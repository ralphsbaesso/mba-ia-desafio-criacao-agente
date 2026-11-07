"""Leitura somente-leitura dos arquivos de dados/ (estado inicial do condomínio)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from aurora import config


def _ler(nome: str) -> Any:
    with open(config.DADOS / nome, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def apartamentos() -> tuple[dict, ...]:
    return tuple(_ler("apartamentos.json"))


@lru_cache(maxsize=None)
def areas() -> tuple[dict, ...]:
    return tuple(_ler("areas.json"))


def area_por_id(area_id: str) -> dict | None:
    return next((a for a in areas() if a["id"] == area_id), None)


def apartamento_existe(numero: str) -> bool:
    return any(a["numero"] == numero for a in apartamentos())


def reservas_iniciais() -> list[dict]:
    return _ler("reservas.json")


def visitantes_iniciais() -> list[dict]:
    return _ler("visitantes.json")
