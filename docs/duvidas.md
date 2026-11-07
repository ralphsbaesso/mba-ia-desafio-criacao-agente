# Dúvidas e pontos em aberto

Registro de decisões tomadas sem confirmação durante a execução. Reavaliar ao final.

1. **Versão do ADK**: fixada em `2.14.0` (a mais recente na data de execução). O enunciado cita testes em 2.2.0 e 2.9.1; a API de confirmação foi verificada diretamente no código-fonte da 2.14.0.
2. **Modelo Gemini**: padrão `gemini-3.5-flash`, configurável por `GEMINI_MODEL`. Os limites gratuitos mudam com frequência; se o avaliador tiver quota só em outro modelo, basta trocar no `.env`.
3. **Chave de API**: não havia chave disponível durante a execução. Os testes automatizados usam dublês do runner; o fluxo completo do avaliador deve ser repetido com uma chave real antes da entrega (há um roteiro em `docs/tasks/`).
4. **Restauração limpa sessões**: `aurora-restaurar` também esvazia as tabelas de `var/sessoes.db` (sem apagar o arquivo). O enunciado deixa livre; escolhemos limpar para que o passo 1 parta de um estado conhecido.
5. **Apartamento inexistente** em `POST /sessoes`: respondemos `422`.
