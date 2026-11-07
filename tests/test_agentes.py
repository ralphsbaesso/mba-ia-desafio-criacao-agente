from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.tools.agent_tool import AgentTool

from aurora import config
from aurora.agents import fabrica
from aurora.agents.app import criar_app


class LlmFalso(BaseLlm):
    model: str = "falso"

    async def generate_content_async(self, llm_request, stream=False):  # pragma: no cover
        raise NotImplementedError
        yield


def _agentes(raiz: LlmAgent) -> list[LlmAgent]:
    todos = [raiz]
    for sub in raiz.sub_agents:
        todos.extend(_agentes(sub))
    for t in raiz.tools:
        if isinstance(t, AgentTool):
            todos.append(t.agent)
    return todos


def test_topologia():
    raiz = fabrica.criar_agentes(LlmFalso())
    assert raiz.name == "principal" and [s.name for s in raiz.sub_agents] == ["reservas", "visitantes"]
    nomes = {a.name for a in _agentes(raiz)}
    assert nomes == {"principal", "reservas", "visitantes", "regulamento"}
    for a in raiz.sub_agents:
        assert any(isinstance(t, AgentTool) and t.agent.name == "regulamento" for t in a.tools)


def test_criar_app_varias_vezes_e_modelo_isolado():
    criar_app(LlmFalso())
    criar_app(LlmFalso())
    app = criar_app()
    assert app.name == "aurora"
    for a in _agentes(fabrica.criar_agentes(LlmFalso())):
        assert isinstance(a.model, LlmFalso)
    assert all(not isinstance(a.model, LlmFalso) for a in _agentes(app.root_agent))


def test_nenhum_agente_recebe_o_regulamento():
    linhas = {
        l.strip()
        for l in (config.DADOS / "regulamento.md").read_text(encoding="utf-8").splitlines()
        if len(l.strip()) > 40
    }
    for a in _agentes(fabrica.criar_agentes(LlmFalso())):
        instrucao = a.instruction if isinstance(a.instruction, str) else ""
        assert "Capítulo" not in instrucao and "Art." not in instrucao
        assert not any(l in instrucao for l in linhas), a.name
