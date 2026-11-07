# Dúvidas e pontos em aberto

Registro de decisões tomadas sem confirmação durante a execução. Reavaliar ao final.

1. **Versão do ADK**: fixada em `2.14.0` (a mais recente na data de execução, 2026-11-07). O enunciado cita testes em 2.2.0 e 2.9.1; a API de confirmação foi verificada diretamente no código-fonte da 2.14.0 e exercitada pelos testes de integração com o `Runner` real.
2. **Modelo Gemini**: padrão `gemini-3.5-flash`, configurável por `GEMINI_MODEL`. Confirmado com chave real em 2026-11-07 (disponível e com quota suficiente para o fluxo completo).
3. **Validação com chave real (task 09)**: concluída em 2026-11-07. `scripts/fluxo_avaliador.sh` rodou contra a API com Gemini real, incluindo o reinício do passo 13, com 0 falhas. Evidência em `docs/evidencia-fluxo-avaliador.md`.
4. **Restauração limpa sessões**: `aurora-restaurar` também esvazia as tabelas de `var/sessoes.db` (sem apagar o arquivo). O enunciado deixa livre; escolhemos limpar para que o passo 1 parta de um estado conhecido. Deve rodar com a API parada.
5. **Apartamento inexistente** em `POST /sessoes`: respondemos `422`.
6. **Mensagem nova com confirmação pendente**: aceita; a pendência continua listada e nada executa. Verificado apenas com o modelo roteirizado (`tests/test_api.py`); o fluxo do avaliador não exercita esse caso.
7. **Transferência entre especialistas**: liberada (`reservas` ↔ `visitantes`), porque uma transferência proibida derruba o turno com exceção do ADK; a segurança está nas tools, não na topologia.
8. **Um único worker**: o lock por sessão vive em memória, então `aurora-api` sobe com um worker. A exclusividade de reserva não depende disso (está no índice do banco).
9. **Entrega na `main`**: o trabalho foi feito na branch `desafio` e mesclado em `main` por fast-forward.
