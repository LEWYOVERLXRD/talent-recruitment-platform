"""通过独立进程加载实际配置代码，不读取正式 .env 或连接业务库。"""
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

import pytest


@pytest.fixture(scope='module')
def isolated_backend(tmp_path_factory):
    root = tmp_path_factory.mktemp('security_config')
    source = Path(__file__).resolve().parents[1] / 'app'
    shutil.copytree(source, root / 'app', ignore=shutil.ignore_patterns('__pycache__'))
    return root


def probe(root, code, key=None):
    env = dict(os.environ)
    for name in ('SECRET_KEY', 'PYTHONPATH', 'DB_PASSWORD', 'ADMIN_PASSWORD', 'LLM_API_KEY'):
        env.pop(name, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    if key is not None:
        env['SECRET_KEY'] = key
    return subprocess.run([sys.executable, '-B', '-c', code], cwd=root, env=env,
                          capture_output=True, text=True, encoding='utf-8', timeout=30)


@pytest.mark.parametrize('key', [None, '', ' ' * 40, 'change-me-in-production',
                               'YOUR_RANDOM_SIGNING_SECRET_AT_LEAST_32_CHARACTERS', 'short'],
                         ids=['missing', 'empty', 'whitespace', 'legacy-default', 'example', 'short'])
def test_invalid_key_prevents_app_import(isolated_backend, key):
    result = probe(isolated_backend, 'from app.main import app', key)
    assert result.returncode != 0
    assert 'SECRET_KEY' in result.stderr


def test_valid_isolated_key_loads_config(isolated_backend):
    key = secrets.token_urlsafe(48)
    result = probe(isolated_backend,
                   'from app.core.config import settings; print(len(settings.SECRET_KEY) >= 32)', key)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'True'


def test_validation_error_hides_all_input_values(isolated_backend):
    marker = 'SYNTHETIC_PRIVATE_CONFIGURATION_VALUE'
    env_file = isolated_backend / '.env'
    env_file.write_text('DB_PASSWORD=' + marker + '\n', encoding='utf-8')
    try:
        result = probe(isolated_backend, 'from app.core.config import settings')
    finally:
        env_file.unlink()
    assert result.returncode != 0
    assert marker not in result.stdout + result.stderr


def test_config_repr_hides_signing_key(isolated_backend):
    key = secrets.token_urlsafe(48)
    result = probe(isolated_backend, 'from app.core.config import settings; print(repr(settings))', key)
    assert result.returncode == 0, result.stderr
    hidden = key not in result.stdout + result.stderr
    assert hidden


def test_env_example_cannot_start_with_placeholder(isolated_backend):
    source = Path(__file__).resolve().parents[1] / '.env.example'
    destination = isolated_backend / '.env'
    shutil.copyfile(source, destination)
    try:
        result = probe(isolated_backend, 'from app.main import app')
    finally:
        destination.unlink()
    assert result.returncode != 0
    assert 'SECRET_KEY' in result.stderr
