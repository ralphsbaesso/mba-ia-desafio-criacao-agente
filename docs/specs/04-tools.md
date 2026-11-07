# Spec 04: Tools de reservas e visitantes

## Objetivo
Toda leitura e gravação de reservas e visitantes passa por tools (`aurora/agents/tools.py`) que usam o apartamento da sessão e pedem confirmação quando há cobrança ou liberação de acesso.

## Regras comuns
- Tools são funções **síncronas** (`def`): o ADK as executa em um executor (`utils/_sync_runner.py`), então o `sqlite3` bloqueante não trava o event loop.
- Toda tool recebe `tool_context: ToolContext` e obtém `apartamento = tool_context.state.get("apartamento")`. Se ausente, retorna `{"erro": "Sessão sem apartamento."}` e nada executa.
- Nenhuma tool aceita `apartamento` como parâmetro.
- Retornos são dicts simples, em português, sem dados de outros apartamentos.
- **Data canônica**: `normalizar_data(texto)` exige `re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto, re.ASCII)` e `date.fromisoformat` (com `ValueError` capturado); devolve `d.isoformat()`. Qualquer outro formato devolve `{"erro": "Use a data no formato AAAA-MM-DD."}`. Só o valor normalizado chega ao repositório.
- **Área canônica**: `normalizar_area(texto)` aceita o `id` de `dados/areas.json` ou o `nome` (comparação em minúsculas, sem acentos) e devolve sempre o `id`. Desconhecido: erro com a lista de ids válidos.
- `nome` de visitante: NFC, `casefold()` só para comparação de duplicidade, `strip()`, espaços internos colapsados, 2 a 80 caracteres, sem caracteres de controle; senão erro.
- Ao pedir confirmação, a tool define `tool_context.actions.skip_summarization = True`, como o `FunctionTool` do ADK faz no modo estático, para o turno terminar sem o modelo repetir a chamada.
- **Sem pendência duplicada**: antes de pedir confirmação, a tool consulta `tool_context.session.events` (função `aurora.confirmacoes.pendentes`, spec 06) e também `tool_context.actions.requested_tool_confirmations` (pedidos feitos nesta mesma invocação, ainda não persistidos); se já existe pendência com a mesma `acao` e os mesmos `detalhes`, devolve `{"status": "aguardando_confirmacao", "repetida": True}` com `skip_summarization=True`, sem criar outra.

## Tools
### `listar_minhas_reservas()`
Retorna `{"reservas": [{codigo, area, nome_area, data}]}` do apartamento da sessão.

### `verificar_disponibilidade(area, data)`
Retorna `{"area", "nome_area", "data", "disponivel": bool, "taxa": float}`. Nunca informa de quem é a reserva existente.

### `reservar_area(area, data)`
1. Normaliza área e data (erros acima).
2. `situacao_data`: se `outra`, `{"ok": False, "motivo": "A data já está reservada para essa área."}` **sem** pedir confirmação; se `propria`, `{"ok": True, "ja_existia": True, "codigo": <existente>, ...}` sem pedir confirmação (nenhuma cobrança nova).
3. Se `taxa > 0` e `tool_context.tool_confirmation` é `None`: `request_confirmation(hint=..., payload={"acao": "reservar_area", "area": <id>, "nome_area", "data": <AAAA-MM-DD>, "taxa"})`, `skip_summarization=True`, retorna `{"status": "aguardando_confirmacao", "area", "data", "taxa"}`. Nada é gravado.
4. Se `taxa > 0` e `tool_confirmation.confirmed` é `False`: `{"ok": False, "motivo": "Reserva não confirmada pelo morador."}`.
5. Caso contrário (taxa zero, ou confirmado): `repositorio.criar_reserva`. `ocupada` → `{"ok": False, "motivo": ...}`; senão `{"ok": True, "codigo", "area", "nome_area", "data", "taxa"}`.
- A confirmação é dinâmica (`request_confirmation`), não `require_confirmation=True`, para que área sem taxa não gere pendência e data ocupada seja recusada antes de pedir confirmação.

### `cancelar_reserva(codigo: str = "", area: str = "", data: str = "")`
Cancela **uma** reserva **do apartamento da sessão** localizada por `codigo` ou por `area` **e** `data` (normalizados). Strings vazias viram `None`; sem chave completa, `{"ok": False, "motivo": "Informe o código da reserva ou a área e a data."}` e nada é alterado. Sem confirmação. Não encontrada entre as próprias: `{"ok": False, "motivo": "Não encontrei essa reserva entre as suas."}`.

### `listar_meus_visitantes()`
Retorna `{"visitantes": [{nome, data}]}` do apartamento da sessão.

### `autorizar_visitante(nome, data)`
Sempre libera acesso, logo sempre confirma: sem `tool_confirmation` → `request_confirmation(payload={"acao": "autorizar_visitante", "nome", "data"})` e retorna pendente; `confirmed=False` → nada grava; `confirmed=True` → grava (`INSERT OR IGNORE`) e retorna `{"ok": True, "nome", "data"}`.

## Critérios de aceite
- Testes unitários com `ToolContext` falso: cada regra acima, incluindo `"20300420"` recusada, `"Salão de festas"` normalizado para `salao-de-festas`, `cancelar_reserva(area="quadra")` recusado e reserva própria repetida sem confirmação.
- `grep -n "apartamento" aurora/agents/tools.py` mostra o valor vindo apenas de `tool_context.state`.
