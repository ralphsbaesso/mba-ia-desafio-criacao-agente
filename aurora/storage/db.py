"""Conexão e esquema do banco SQLite do condomínio."""

from __future__ import annotations

import sqlite3
import unicodedata
from contextlib import contextmanager
from typing import Iterator

from aurora import config
from aurora.storage import dados_iniciais

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS reservas (
  codigo TEXT PRIMARY KEY,
  apartamento TEXT NOT NULL,
  area TEXT NOT NULL,
  data TEXT NOT NULL CHECK (date(data) = data),
  status TEXT NOT NULL DEFAULT 'ativa' CHECK (status IN ('ativa', 'cancelada'))
);
CREATE UNIQUE INDEX IF NOT EXISTS reservas_area_data_ativa
  ON reservas(area, data) WHERE status = 'ativa';

CREATE TABLE IF NOT EXISTS visitantes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  apartamento TEXT NOT NULL,
  nome TEXT NOT NULL,
  nome_chave TEXT NOT NULL,
  data TEXT NOT NULL CHECK (date(data) = data),
  UNIQUE (apartamento, nome_chave, data)
);

CREATE TABLE IF NOT EXISTS sessoes (
  session_id TEXT PRIMARY KEY,
  apartamento TEXT NOT NULL,
  criada_em TEXT NOT NULL
);
"""


def chave_nome(nome: str) -> str:
    """Chave de unicidade do nome: NFC, sem acentos, casefold, espaços colapsados."""
    base = unicodedata.normalize("NFKD", nome)
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.casefold().split())


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Abre uma conexão por operação. Transações são explícitas (BEGIN ... COMMIT)."""
    conn = sqlite3.connect(config.db_condominio(), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
    finally:
        conn.close()


def _carregar_seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, 'ativa')",
        [(r["codigo"], r["apartamento"], r["area"], r["data"]) for r in dados_iniciais.reservas_iniciais()],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO visitantes (apartamento, nome, nome_chave, data) VALUES (?, ?, ?, ?)",
        [
            (v["apartamento"], v["nome"], chave_nome(v["nome"]), v["data"])
            for v in dados_iniciais.visitantes_iniciais()
        ],
    )
    conn.execute("INSERT OR REPLACE INTO meta (chave, valor) VALUES ('seed', '1')")


def inicializar() -> None:
    """Cria diretório e tabelas; carrega os dados iniciais só na primeira vez (marcador meta.seed)."""
    config.garantir_diretorios()
    with conectar() as conn:
        conn.executescript(ESQUEMA)
        conn.execute("BEGIN IMMEDIATE")
        try:
            ja_carregado = conn.execute("SELECT 1 FROM meta WHERE chave = 'seed'").fetchone()
            if not ja_carregado:
                _carregar_seed(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def restaurar_condominio() -> None:
    """Volta reservas e visitantes ao conteúdo de dados/ e apaga o mapeamento de sessões."""
    config.garantir_diretorios()
    with conectar() as conn:
        conn.executescript(ESQUEMA)
        conn.execute("BEGIN IMMEDIATE")
        try:
            for tabela in ("reservas", "visitantes", "sessoes", "meta"):
                conn.execute(f"DELETE FROM {tabela}")
            _carregar_seed(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def limpar_sessoes_adk() -> None:
    """Esvazia as tabelas do banco de sessões do ADK sem apagar o arquivo.

    O SqliteSessionService cria o esquema de forma preguiçosa, então o arquivo
    pode existir sem tabelas; tabelas ausentes são simplesmente ignoradas.
    """
    caminho = config.db_sessoes()
    if not caminho.exists():
        return
    conn = sqlite3.connect(caminho, timeout=10, isolation_level=None)
    try:
        tabelas = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        # Filhos primeiro: 'sessions' por último evita depender de ON DELETE CASCADE.
        tabelas.sort(key=lambda n: (n == "sessions", n))
        conn.execute("BEGIN IMMEDIATE")
        for tabela in tabelas:
            conn.execute(f'DELETE FROM "{tabela}"')
        conn.execute("COMMIT")
    finally:
        conn.close()
