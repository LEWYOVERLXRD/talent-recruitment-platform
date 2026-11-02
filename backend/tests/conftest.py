"""隔离环境：不加载项目配置，不连接 MySQL，不调用大模型。"""
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import declarative_base

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
database = types.ModuleType('app.core.database')
database.Base = declarative_base()
database.get_db = lambda: None
sys.modules['app.core.database'] = database
config = types.ModuleType('app.core.config')
config.settings = SimpleNamespace(LLM_MODEL='OFFLINE_TEST')
sys.modules['app.core.config'] = config
llm = types.ModuleType('app.services.llm')
llm.chat = Mock(side_effect=AssertionError('External LLM calls prohibited'))
sys.modules['app.services.llm'] = llm
