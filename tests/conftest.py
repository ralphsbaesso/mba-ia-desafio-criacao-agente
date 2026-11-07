import pytest


@pytest.fixture(autouse=True)
def dados_em_tmp(tmp_path, monkeypatch):
    """Redireciona todo o armazenamento para um diretório temporário."""
    monkeypatch.setenv("AURORA_DATA_DIR", str(tmp_path / "var"))
    yield tmp_path / "var"
