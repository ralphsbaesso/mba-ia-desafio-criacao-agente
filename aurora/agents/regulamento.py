"""Consulta ao regulamento interno por capítulo.

O texto completo nunca entra em instruções de agente: a tool devolve apenas
o capítulo mais relevante para o assunto perguntado.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from aurora import config

STOPWORDS = {
    "de", "da", "do", "das", "dos", "que", "aos", "ate", "até", "horas", "hora", "pode", "posso",
    "podem", "qual", "quais", "como", "funciona", "para", "por", "com", "sem", "uma", "um",
    "nos", "nas", "the", "sobre", "tem", "ter", "ser", "esta", "este", "isso", "quando",
    "onde", "quem", "regulamento", "regra", "regras", "condominio", "residencial", "aurora",
    "permitido", "proibido", "existe", "preciso", "quero", "gostaria", "saber", "dia", "dias",
    "apartamento", "apartamentos", "morador", "moradores", "meu", "minha", "aqui", "predio",
}
PREFIXO = 5
# Palavras do dia a dia que o regulamento não usa, mapeadas para o termo do texto.
SINONIMOS = {
    "cachorro": "animais", "cachorros": "animais", "gato": "animais", "gatos": "animais",
    "pet": "animais", "pets": "animais", "cao": "animais", "caes": "animais", "bicho": "animais",
    "festa": "salao", "aniversario": "salao", "carro": "veiculos", "moto": "veiculos",
    "entregador": "portaria", "entrega": "portaria", "visita": "visitantes",
}


@dataclass(frozen=True)
class Capitulo:
    titulo: str
    texto: str


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def _termos(texto: str) -> list[str]:
    palavras = re.findall(r"[a-z0-9]+", normalizar(texto))
    palavras = [SINONIMOS.get(p, p) for p in palavras]
    return [p[:PREFIXO] for p in palavras if len(p) >= 3 and p not in STOPWORDS]


@lru_cache(maxsize=1)
def capitulos() -> tuple[Capitulo, ...]:
    conteudo = (config.DADOS / "regulamento.md").read_text(encoding="utf-8")
    partes = re.split(r"^(?=## )", conteudo, flags=re.M)
    resultado = []
    for parte in partes:
        if not parte.startswith("## "):
            continue
        titulo, _, corpo = parte.partition("\n")
        resultado.append(Capitulo(titulo=titulo[3:].strip(), texto=parte.strip()))
    return tuple(resultado)


def _pontuar(capitulo: Capitulo, termos: list[str]) -> int:
    titulo = _termos(capitulo.titulo)
    corpo = _termos(capitulo.texto)
    pontos = 0
    for termo in set(termos):
        pontos += corpo.count(termo)
        pontos += 3 * titulo.count(termo)
    return pontos


def buscar_capitulo(assunto: str) -> Capitulo | None:
    termos = _termos(assunto)
    if not termos:
        return None
    melhor = max(capitulos(), key=lambda c: _pontuar(c, termos))
    return melhor if _pontuar(melhor, termos) > 0 else None


def consultar_regulamento(assunto: str) -> dict:
    """Devolve o capítulo do regulamento interno mais relacionado ao assunto.

    Args:
        assunto: tema da dúvida do morador, por exemplo "horário da piscina aos domingos".

    Returns:
        {"capitulo": {"titulo", "texto"}} com o capítulo mais relevante, ou
        {"capitulos_disponiveis": [...]} quando nenhum capítulo corresponde ao assunto.
    """
    capitulo = buscar_capitulo(assunto)
    if capitulo is None:
        return {"capitulos_disponiveis": [c.titulo for c in capitulos()]}
    return {"capitulo": {"titulo": capitulo.titulo, "texto": capitulo.texto}}
