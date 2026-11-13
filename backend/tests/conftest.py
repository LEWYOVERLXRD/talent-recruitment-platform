"""隔离环境：不加载项目配置，不连接 MySQL，不调用大模型。"""
import sys
import types
import secrets
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import declarative_base

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
database = types.ModuleType('app.core.database')
database.Base = declarative_base()
database.get_db = lambda: None
database.verify_db_ready = lambda *args, **kwargs: None
database.init_db = lambda *args, **kwargs: None
sys.modules['app.core.database'] = database
config = types.ModuleType('app.core.config')
config.settings = SimpleNamespace(
    LLM_MODEL='OFFLINE_TEST', SECRET_KEY=secrets.token_urlsafe(48),
    ALGORITHM='HS256', ACCESS_TOKEN_EXPIRE_MINUTES=30,
    DB_ECHO=False, get_database_url=lambda: 'sqlite:///:memory:')
sys.modules['app.core.config'] = config
llm = types.ModuleType('app.services.llm')
llm.chat = Mock(side_effect=AssertionError('External LLM calls prohibited'))
# 兼容既有业务测试的纯文本替身；实际模型来源由真实封装的集成测试验证。
llm.chat_with_model = lambda system, user: SimpleNamespace(
    content=llm.chat(system, user), model_used=config.settings.LLM_MODEL)
sys.modules['app.services.llm'] = llm
