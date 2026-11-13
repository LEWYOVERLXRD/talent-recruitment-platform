"""MySQL 结构快照与差异比较（只读）。

用途：
1. 审计正式库/恢复库的真实结构（表、列、索引、外键、CHECK、生成列、字符集）。
2. 在 ``alembic stamp`` 之前，确认存量库与 Alembic 基线完全一致。
3. 对比“空库 upgrade head”与“存量库接入”两条路径的最终结构。

本模块只执行 SELECT / SHOW 语句，不读取业务行内容，不修改数据库。
``alembic_version`` 属于迁移工具自身的元数据，不计入业务结构比较。
"""
from __future__ import annotations

import re
from typing import Any

IGNORED_TABLES = frozenset({"alembic_version"})

_AUTO_INCREMENT = re.compile(r"\s+AUTO_INCREMENT=\d+")


def _rows(connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        names = [column[0].lower() for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def normalize_create_table(ddl: str) -> str:
    """去掉自增计数器及冗余的字符集声明，用于结构等价比较。"""
    ddl = _AUTO_INCREMENT.sub("", ddl).strip()
    # MySQL 在 utf8mb4 字符集下，字段声明 CHARACTER SET utf8mb4 COLLATE xxx 与 COLLATE xxx 完全等价
    ddl = re.sub(r"CHARACTER SET utf8mb4 COLLATE ", "COLLATE ", ddl)
    return ddl


def capture(connection, schema: str) -> dict[str, Any]:
    """读取 ``schema`` 的完整结构，返回可 JSON 序列化的规范化字典。

    ``connection`` 为 PyMySQL 连接；调用方负责将会话设为只读。
    """
    tables = _rows(connection, """
        SELECT TABLE_NAME, ENGINE, TABLE_COLLATION, ROW_FORMAT, CREATE_OPTIONS, TABLE_COMMENT
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'
        ORDER BY TABLE_NAME""", (schema,))
    names = [row["table_name"] for row in tables if row["table_name"] not in IGNORED_TABLES]

    columns = _rows(connection, """
        SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT,
               EXTRA, GENERATION_EXPRESSION, CHARACTER_SET_NAME, COLLATION_NAME, COLUMN_COMMENT,
               COLUMN_KEY
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s
        ORDER BY TABLE_NAME, ORDINAL_POSITION""", (schema,))
    statistics = _rows(connection, """
        SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, SUB_PART,
               INDEX_TYPE, EXPRESSION, IS_VISIBLE
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA=%s
        ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX""", (schema,))
    foreign_keys = _rows(connection, """
        SELECT k.TABLE_NAME, k.CONSTRAINT_NAME, k.ORDINAL_POSITION, k.COLUMN_NAME,
               k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME, r.UPDATE_RULE, r.DELETE_RULE
        FROM information_schema.KEY_COLUMN_USAGE k
        JOIN information_schema.REFERENTIAL_CONSTRAINTS r
          ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME
         AND r.TABLE_NAME=k.TABLE_NAME
        WHERE k.TABLE_SCHEMA=%s AND k.REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY k.TABLE_NAME, k.CONSTRAINT_NAME, k.ORDINAL_POSITION""", (schema,))
    checks = _rows(connection, """
        SELECT t.TABLE_NAME, c.CONSTRAINT_NAME, c.CHECK_CLAUSE, t.ENFORCED
        FROM information_schema.CHECK_CONSTRAINTS c
        JOIN information_schema.TABLE_CONSTRAINTS t
          ON t.CONSTRAINT_SCHEMA=c.CONSTRAINT_SCHEMA AND t.CONSTRAINT_NAME=c.CONSTRAINT_NAME
         AND t.CONSTRAINT_TYPE='CHECK'
        WHERE c.CONSTRAINT_SCHEMA=%s
        ORDER BY t.TABLE_NAME, c.CONSTRAINT_NAME""", (schema,))

    result: dict[str, Any] = {}
    for meta in tables:
        name = meta["table_name"]
        if name in IGNORED_TABLES:
            continue
        with connection.cursor() as cursor:
            cursor.execute(f"SHOW CREATE TABLE `{schema}`.`{name}`")
            ddl = cursor.fetchone()[1]
        indexes: dict[str, dict[str, Any]] = {}
        for row in (r for r in statistics if r["table_name"] == name):
            index = indexes.setdefault(row["index_name"], {
                "unique": not bool(row["non_unique"]),
                "type": row["index_type"],
                "visible": row["is_visible"],
                "columns": [],
            })
            index["columns"].append(row["column_name"] if row["expression"] is None
                                    else {"expression": row["expression"]})
            if row["sub_part"] is not None:
                index.setdefault("sub_parts", {})[str(row["seq_in_index"])] = row["sub_part"]
        fks: dict[str, dict[str, Any]] = {}
        for row in (r for r in foreign_keys if r["table_name"] == name):
            fk = fks.setdefault(row["constraint_name"], {
                "columns": [], "referred_table": row["referenced_table_name"],
                "referred_columns": [], "on_update": row["update_rule"],
                "on_delete": row["delete_rule"],
            })
            fk["columns"].append(row["column_name"])
            fk["referred_columns"].append(row["referenced_column_name"])
        result[name] = {
            "engine": meta["engine"],
            "collation": meta["table_collation"],
            "row_format": meta["row_format"],
            "create_options": meta["create_options"],
            "comment": meta["table_comment"],
            "columns": [
                {
                    "name": c["column_name"],
                    "type": c["column_type"],
                    "nullable": c["is_nullable"] == "YES",
                    "default": c["column_default"],
                    "extra": c["extra"],
                    "generated": c["generation_expression"] or None,
                    "charset": c["character_set_name"],
                    "collation": c["collation_name"],
                    "comment": c["column_comment"],
                }
                for c in columns if c["table_name"] == name
            ],
            "indexes": dict(sorted(indexes.items())),
            "foreign_keys": dict(sorted(fks.items())),
            "checks": {c["constraint_name"]: {"clause": c["check_clause"], "enforced": c["enforced"]}
                       for c in checks if c["table_name"] == name},
            "create_table": normalize_create_table(ddl),
        }
    return result


def diff(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """返回人类可读的差异列表；空列表表示结构完全一致。"""
    problems: list[str] = []
    for name in sorted(set(expected) - set(actual)):
        problems.append(f"缺少表 {name}")
    for name in sorted(set(actual) - set(expected)):
        problems.append(f"多出表 {name}")
    for name in sorted(set(expected) & set(actual)):
        left, right = expected[name], actual[name]
        for key in ("engine", "collation", "row_format", "create_options", "comment"):
            if left[key] != right[key]:
                problems.append(f"{name}: 表属性 {key} 期望 {left[key]!r} 实际 {right[key]!r}")
        left_cols = {c["name"]: c for c in left["columns"]}
        right_cols = {c["name"]: c for c in right["columns"]}
        for col in sorted(set(left_cols) - set(right_cols)):
            problems.append(f"{name}: 缺少列 {col}")
        for col in sorted(set(right_cols) - set(left_cols)):
            problems.append(f"{name}: 多出列 {col}")
        for col in sorted(set(left_cols) & set(right_cols)):
            for key, value in left_cols[col].items():
                if right_cols[col][key] != value:
                    problems.append(f"{name}.{col}: {key} 期望 {value!r} 实际 {right_cols[col][key]!r}")
        if [c["name"] for c in left["columns"]] != [c["name"] for c in right["columns"]]:
            problems.append(f"{name}: 列顺序不同")
        for section in ("indexes", "foreign_keys", "checks"):
            for item in sorted(set(left[section]) - set(right[section])):
                problems.append(f"{name}: 缺少 {section} {item}")
            for item in sorted(set(right[section]) - set(left[section])):
                problems.append(f"{name}: 多出 {section} {item}")
            for item in sorted(set(left[section]) & set(right[section])):
                if left[section][item] != right[section][item]:
                    problems.append(f"{name}: {section} {item} 期望 {left[section][item]!r} "
                                    f"实际 {right[section][item]!r}")
        if left["create_table"] != right["create_table"]:
            problems.append(f"{name}: SHOW CREATE TABLE 文本不同")
    return problems
