import pytest

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('SONICFORGE_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('SONICFORGE_CACHE_DIR',str(tmp_path/'cache'))
    monkeypatch.setenv('SONICFORGE_ENABLE_FAKE','1')
    monkeypatch.setenv('SONICFORGE_SETUP_TEST_MODE','1')
    return tmp_path
