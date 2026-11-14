"""新增企业面试题组表 interview_question_sets

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14 02:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """在 0001 基线之上新增 interview_question_sets 题组表。"""
    op.create_table(
        "interview_question_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("recommendation_id", sa.Integer(), nullable=False, comment="来源推荐ID"),
        sa.Column("job_id", sa.Integer(), nullable=False, comment="招聘需求ID"),
        sa.Column("candidate_id", sa.Integer(), nullable=False, comment="候选人ID"),
        sa.Column("created_by", sa.Integer(), nullable=False, comment="生成操作人ID"),
        sa.Column("recommendation_version", sa.Integer(), nullable=False, comment="生成时的推荐版本号"),
        sa.Column("recommendation_status", sa.String(length=20), nullable=False, comment="生成时的推荐状态"),
        sa.Column("model_used", sa.String(length=100), nullable=False, comment="实际使用的模型名称"),
        sa.Column("input_summary", sa.JSON(), nullable=False, comment="脱敏后的固定输入摘要"),
        sa.Column("questions", sa.JSON(), nullable=False, comment="结构化面试题数组"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], name="fk_iqs_recommendation_id"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_iqs_job_id"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name="fk_iqs_candidate_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_iqs_created_by"),
        sa.CheckConstraint("recommendation_status IN ('accepted', 'interviewing')", name="ck_iqs_rec_status"),
        sa.CheckConstraint("recommendation_version > 0", name="ck_iqs_rec_version"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_iqs_recommendation_created",
        "interview_question_sets",
        ["recommendation_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """回退 0002 新增的 interview_question_sets 表（不影响 0001 基线）。"""
    op.drop_index("ix_iqs_recommendation_created", table_name="interview_question_sets")
    op.drop_table("interview_question_sets")
