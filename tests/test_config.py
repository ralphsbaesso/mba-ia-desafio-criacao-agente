import os

from aurora import config


def test_valor_vazio_usa_padrao(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "")
    assert config.modelo() == config.MODELO_PADRAO


def test_data_dir_relativo_resolve_contra_raiz(monkeypatch):
    monkeypatch.setenv("AURORA_DATA_DIR", "pasta")
    assert config.data_dir() == config.RAIZ / "pasta"
    assert config.db_condominio().name == "aurora.db"
    assert config.db_sessoes().name == "sessoes.db"


def test_data_dir_absoluto(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_DATA_DIR", str(tmp_path))
    assert config.data_dir() == tmp_path


def test_garantir_diretorios_cria_pasta(dados_em_tmp):
    assert not dados_em_tmp.exists()
    config.garantir_diretorios()
    assert dados_em_tmp.is_dir()


def test_env_da_raiz_e_carregado(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("AURORA_TESTE_ENV=valor\n")
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.delenv("AURORA_TESTE_ENV", raising=False)
    config.carregar_env(tmp_path)
    assert os.environ["AURORA_TESTE_ENV"] == "valor"
