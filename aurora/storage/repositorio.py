"""Operações sobre reservas, visitantes e sessões.

Toda função recebe o apartamento explicitamente; quem chama (as tools) o obtém
da sessão. Datas chegam já no formato canônico AAAA-MM-DD.
"""

from __future__ import annotations

import secrets
import sqlite3
import string
from dataclasses import dataclass
from datetime import datetime, timezone

from datetime import date

from aurora.storage import dados_iniciais, db

_ALFABETO = string.ascii_uppercase + string.digits


def gerar_codigo() -> str:
    return "RSV-" + "".join(secrets.choice(_ALFABETO) for _ in range(6))


@dataclass(frozen=True)
class Resultado:
    ok: bool
    codigo: str | None = None
    motivo: str | None = None
    ja_existia: bool = False


def validar_data(data: str) -> str:
    """Defesa em profundidade: só aceita AAAA-MM-DD de um dia que existe."""
    if len(data) != 10 or date.fromisoformat(data).isoformat() != data:
        raise ValueError(f"Data inválida: {data!r}")
    return data


def validar_area(area: str) -> str:
    if dados_iniciais.area_por_id(area) is None:
        raise ValueError(f"Área desconhecida: {area!r}")
    return area


def listar_reservas(apartamento: str) -> list[dict]:
    with db.conectar() as conn:
        linhas = conn.execute(
            "SELECT codigo, area, data FROM reservas WHERE apartamento = ? AND status = 'ativa' ORDER BY data, codigo",
            (apartamento,),
        ).fetchall()
    return [dict(l) for l in linhas]


def data_disponivel(area: str, data: str) -> bool:
    with db.conectar() as conn:
        linha = conn.execute(
            "SELECT 1 FROM reservas WHERE area = ? AND data = ? AND status = 'ativa'", (area, data)
        ).fetchone()
    return linha is None


def _situacao(conn: sqlite3.Connection, apartamento: str, area: str, data: str) -> tuple[str, str | None]:
    linha = conn.execute(
        "SELECT codigo, apartamento FROM reservas WHERE area = ? AND data = ? AND status = 'ativa'",
        (area, data),
    ).fetchone()
    if linha is None:
        return "livre", None
    if linha["apartamento"] == apartamento:
        return "propria", linha["codigo"]
    return "outra", None


def situacao_data(apartamento: str, area: str, data: str) -> tuple[str, str | None]:
    """Devolve ("livre" | "propria" | "outra", codigo_se_propria). Nunca expõe o apartamento dono."""
    with db.conectar() as conn:
        return _situacao(conn, apartamento, area, data)


def criar_reserva(apartamento: str, area: str, data: str) -> Resultado:
    """Grava a reserva. A exclusividade é garantida pelo índice único parcial no INSERT."""
    validar_area(area)
    validar_data(data)
    with db.conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            situacao, codigo_existente = _situacao(conn, apartamento, area, data)
            if situacao == "propria":
                conn.execute("COMMIT")
                return Resultado(ok=True, codigo=codigo_existente, ja_existia=True)
            for _ in range(5):
                codigo = gerar_codigo()
                try:
                    conn.execute(
                        "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, 'ativa')",
                        (codigo, apartamento, area, data),
                    )
                except sqlite3.IntegrityError as e:
                    if "reservas.codigo" in str(e):
                        continue  # colisão de código: sorteia outro
                    if "reservas.area" in str(e):
                        conn.execute("ROLLBACK")
                        return Resultado(ok=False, motivo="ocupada")
                    raise
                conn.execute("COMMIT")
                return Resultado(ok=True, codigo=codigo)
            conn.execute("ROLLBACK")
            raise RuntimeError("Não foi possível gerar um código de reserva único.")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def cancelar_reserva(
    apartamento: str,
    codigo: str | None = None,
    area: str | None = None,
    data: str | None = None,
) -> dict | None:
    """Cancela uma única reserva ativa do apartamento. Exige codigo ou (area e data)."""
    if codigo:
        filtro, params = "codigo = ?", (codigo.strip().upper(),)
    elif area and data:
        filtro, params = "area = ? AND data = ?", (validar_area(area), validar_data(data))
    else:
        raise ValueError("Informe o código da reserva ou a área e a data.")
    with db.conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            alvo = conn.execute(
                f"SELECT codigo, area, data FROM reservas WHERE apartamento = ? AND status = 'ativa' AND {filtro}",
                (apartamento, *params),
            ).fetchall()
            if len(alvo) != 1:
                conn.execute("ROLLBACK")
                return None
            cur = conn.execute(
                "UPDATE reservas SET status = 'cancelada' WHERE codigo = ? AND apartamento = ? AND status = 'ativa'",
                (alvo[0]["codigo"], apartamento),
            )
            if cur.rowcount != 1:
                conn.execute("ROLLBACK")
                return None
            conn.execute("COMMIT")
            return dict(alvo[0])
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def listar_visitantes(apartamento: str) -> list[dict]:
    with db.conectar() as conn:
        linhas = conn.execute(
            "SELECT nome, data FROM visitantes WHERE apartamento = ? ORDER BY data, nome", (apartamento,)
        ).fetchall()
    return [dict(l) for l in linhas]


def autorizar_visitante(apartamento: str, nome: str, data: str) -> None:
    validar_data(data)
    with db.conectar() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO visitantes (apartamento, nome, nome_chave, data) VALUES (?, ?, ?, ?)",
            (apartamento, nome, db.chave_nome(nome), data),
        )


def registrar_sessao(session_id: str, apartamento: str) -> None:
    with db.conectar() as conn:
        conn.execute(
            "INSERT INTO sessoes (session_id, apartamento, criada_em) VALUES (?, ?, ?)",
            (session_id, apartamento, datetime.now(timezone.utc).isoformat()),
        )


def apartamento_da_sessao(session_id: str) -> str | None:
    with db.conectar() as conn:
        linha = conn.execute("SELECT apartamento FROM sessoes WHERE session_id = ?", (session_id,)).fetchone()
    return linha["apartamento"] if linha else None


def restaurar() -> None:
    """Restaura o estado inicial: limpa as sessões do ADK e depois o banco do condomínio."""
    db.limpar_sessoes_adk()
    db.restaurar_condominio()
