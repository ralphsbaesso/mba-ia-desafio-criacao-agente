"""Configuração da aplicação.

Todos os valores são lidos em tempo de chamada (funções, não constantes),
para que testes possam redirecionar caminhos com variáveis de ambiente.
Valor vazio conta como ausente e cai no padrão.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "dados"


def carregar_env(raiz: Path = RAIZ) -> None:
    """Carrega o .env da raiz do repositório, sem sobrescrever o ambiente."""
    load_dotenv(raiz / ".env", override=False)


carregar_env()

MODELO_PADRAO = "gemini-3.5-flash"


def _env(nome: str, padrao: str) -> str:
    return os.getenv(nome) or padrao


def modelo() -> str:
    return _env("GEMINI_MODEL", MODELO_PADRAO)


def data_dir() -> Path:
    caminho = Path(_env("AURORA_DATA_DIR", "var"))
    if not caminho.is_absolute():
        caminho = RAIZ / caminho
    return caminho


def db_condominio() -> Path:
    return data_dir() / "aurora.db"


def db_sessoes() -> Path:
    return data_dir() / "sessoes.db"


def host() -> str:
    return _env("AURORA_HOST", "127.0.0.1")


def porta() -> int:
    valor = _env("AURORA_PORT", "8000")
    try:
        return int(valor)
    except ValueError as e:
        raise SystemExit(f"AURORA_PORT inválida: {valor!r} (use um número).") from e


def api_key_configurada() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY"))


def garantir_diretorios() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
