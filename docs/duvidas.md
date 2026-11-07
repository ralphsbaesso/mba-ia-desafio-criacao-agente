# Dúvidas e pontos em aberto

Registro de decisões tomadas sem confirmação durante a execução. Reavaliar ao final.

1. **Versão do ADK**: fixada em `2.14.0` (a mais recente na data de execução, 2026-11-07). O enunciado cita testes em 2.2.0 e 2.9.1; a API de confirmação foi verificada diretamente no código-fonte da 2.14.0 e exercitada pelos testes de integração com o `Runner` real.
2. **Modelo Gemini**: padrão `gemini-3.5-flash`, configurável por `GEMINI_MODEL`. Não foi possível confirmar nome e quota sem chave; se o avaliador tiver quota em outro modelo, basta trocar no `.env`.
3. **Validação com chave real (task 09, pendente)**: não havia `GOOGLE_API_KEY` disponível durante a execução. Toda a lógica foi provada com um modelo roteirizado e o `Runner`/`SqliteSessionService` reais (`tests/test_integracao.py`, `tests/test_api.py`), e o clone limpo foi exercitado com `uv sync`, `aurora-restaurar` e `aurora-api`. Falta rodar `scripts/fluxo_avaliador.sh` contra a API com Gemini de verdade, o que depende de o modelo seguir as instruções (transferências, escolha de tools, não repetir a chamada quando há pendência). Isso deve ser feito antes da entrega e, se o comportamento do modelo divergir, ajustar as instruções em `aurora/agents/fabrica.py`.
4. **Restauração limpa sessões**: `aurora-restaurar` também esvazia as tabelas de `var/sessoes.db` (sem apagar o arquivo). O enunciado deixa livre; escolhemos limpar para que o passo 1 parta de um estado conhecido. Deve rodar com a API parada.
5. **Apartamento inexistente** em `POST /sessoes`: respondemos `422`.
6. **Mensagem nova com confirmação pendente**: aceita; a pendência continua listada e nada executa. Não foi verificado com o Gemini real se o histórico com um pedido de confirmação em aberto é aceito pelo modelo (o ADK filtra esse evento ao montar o prompt, então o risco é baixo).
7. **Transferência entre especialistas**: liberada (`reservas` ↔ `visitantes`), porque uma transferência proibida derruba o turno com exceção do ADK; a segurança está nas tools, não na topologia.
8. **Um único worker**: o lock por sessão vive em memória, então `aurora-api` sobe com um worker. A exclusividade de reserva não depende disso (está no índice do banco).
9. **Entrega na `main`**: o trabalho foi feito na branch `desafio`; o enunciado pede tudo na `main`. Fazer o merge ao final.
