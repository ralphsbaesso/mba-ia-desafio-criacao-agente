"""Modelo falso determinístico para testes de integração sem rede.

Decide a próxima ação olhando as tools disponíveis para o agente e a última
mensagem do histórico, imitando o que o Gemini faria no fluxo do avaliador.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types


def _norm(s: str) -> str:
    base = unicodedata.normalize("NFKD", s)
    return "".join(c for c in base if not unicodedata.combining(c)).lower()


def _data(texto: str) -> str | None:
    m = re.search(r"\d{4}-\d{2}-\d{2}", texto)
    return m.group(0) if m else None


def _area(texto: str) -> str | None:
    t = _norm(texto)
    if "salao" in t:
        return "salao-de-festas"
    if "churrasqueira" in t:
        return "churrasqueira"
    if "quadra" in t:
        return "quadra"
    return None


class LlmRoteirizado(BaseLlm):
    model: str = "roteirizado"
    falhar_proxima_chamada: bool = False
    falhar_apos_pedido: bool = False
    chamadas: int = 0

    def _texto(self, texto: str) -> LlmResponse:
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=texto)]))

    def _chamada(self, nome: str, args: dict) -> LlmResponse:
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name=nome, args=args))])
        )

    def _decidir(self, req: LlmRequest) -> LlmResponse:
        tools = set(req.tools_dict.keys())
        ultimo = req.contents[-1] if req.contents else None
        partes = list(ultimo.parts or []) if ultimo else []

        respostas = [p.function_response for p in partes if p.function_response and p.function_response.name != "transfer_to_agent"]
        if respostas:
            fr = respostas[-1]
            r = fr.response or {}
            if fr.name == "regulamento":
                return self._texto(str(r.get("result", r)))
            if fr.name == "consultar_regulamento":
                cap = r.get("capitulo") or {}
                m = re.search(r"domingos e feriados, a piscina funciona das (\S+) às (\S+)\.", cap.get("texto", ""))
                return self._texto(f"Aos domingos a piscina fecha às {m.group(2)} (Art. 22)." if m else "Não encontrei.")
            if r.get("status") == "aguardando_confirmacao":
                return self._texto("Pedido aguardando confirmação.")
            return self._texto("Resultado: " + json.dumps(r, ensure_ascii=False))

        # Após uma transferência, a última mensagem é a resposta de transfer_to_agent:
        # usa o último texto do usuário.
        texto = ""
        for c in reversed(req.contents):
            if c.role != "user" or not any(p.text for p in c.parts or []):
                continue
            candidato = "".join(p.text or "" for p in c.parts if p.text)
            if candidato.startswith("For context:"):
                continue  # transcrição de outro agente injetada pelo ADK
            texto = candidato
            break
        t = _norm(texto)
        if "piscina" in t or "regulamento" in t:
            if "consultar_regulamento" in tools:
                return self._chamada("consultar_regulamento", {"assunto": texto})
            if "regulamento" in tools:
                return self._chamada("regulamento", {"request": texto})
        if "visitante" in t or "entrada" in t or "libera" in t:
            if "autorizar_visitante" in tools:
                m = re.search(r"(?:da|do|de) ([A-ZÀ-Ú][\w]+ [A-ZÀ-Ú][\w]+)", texto)
                return self._chamada("autorizar_visitante", {"nome": m.group(1) if m else "Visitante X", "data": _data(texto)})
            if "transfer_to_agent" in tools:
                return self._chamada("transfer_to_agent", {"agent_name": "visitantes"})
        if "cancel" in t:
            if "cancelar_reserva" in tools:
                return self._chamada("cancelar_reserva", {"area": _area(texto) or "", "data": _data(texto) or ""})
            if "transfer_to_agent" in tools:
                return self._chamada("transfer_to_agent", {"agent_name": "reservas"})
        if "reserv" in t:
            if "reservar_area" in tools and _area(texto) and _data(texto):
                return self._chamada("reservar_area", {"area": _area(texto), "data": _data(texto)})
            if "listar_minhas_reservas" in tools:
                return self._chamada("listar_minhas_reservas", {})
            if "transfer_to_agent" in tools:
                return self._chamada("transfer_to_agent", {"agent_name": "reservas"})
        return self._texto("Posso ajudar com reservas, visitantes e regulamento.")

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        self.chamadas += 1
        if self.falhar_proxima_chamada:
            self.falhar_proxima_chamada = False
            raise RuntimeError("modelo indisponível (simulado)")
        if self.falhar_apos_pedido:
            ultimo = llm_request.contents[-1] if llm_request.contents else None
            for p in (ultimo.parts or []) if ultimo else []:
                if p.function_response and (p.function_response.response or {}).get("status") == "aguardando_confirmacao":
                    self.falhar_apos_pedido = False
                    raise RuntimeError("modelo indisponível após o pedido (simulado)")
        yield self._decidir(llm_request)
