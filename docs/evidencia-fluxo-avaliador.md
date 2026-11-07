# Evidência: fluxo do avaliador com Gemini real

Execução de `scripts/fluxo_avaliador.sh` em 2026-11-07 contra a API local
(`uv run aurora-restaurar` + `uv run aurora-api`), com `GOOGLE_API_KEY` válida
e o modelo padrão `gemini-3.5-flash`. No passo 13 a API foi parada com Ctrl+C e
subida de novo sem restaurar os dados. Todos os 14 passos passaram (0 falhas).

```bash
scripts/fluxo_avaliador.sh                                                                                                                                                                        12:19:29.743
Passo 1
  ok: 101 tem RSV-1377
  ok: 302 tem Marina Duarte
Passo 2
  ok: POST /sessoes responde 201
  S1=95961b90-16a6-453f-a452-c31f19c2b1f7
Passo 3
  ok: resposta sem dados do 302
  ok: passo 3: sem confirmação pendente
  ok: eventos sem dados do 302
Passo 4
  ok: resposta sem RSV-4821
  ok: passo 4: sem confirmação pendente
  ok: 302 ainda tem RSV-4821
  ok: eventos sem RSV-4821
Passo 5
  ok: passo 5: sem confirmação pendente
  ok: RSV-1377 cancelada
Passo 6
  ok: passo 6: sem confirmação pendente
  ok: quadra 2030-04-06 reservada
Passo 7
  ok: pendência com área e data
  ok: salão ainda não reservado
  ok: negar não grava
Passo 8
  ok: exatamente uma reserva do salão
  ok: reenvio recebe 409
  ok: continua uma reserva
Passo 9
  ok: id inexistente recebe 409
  ok: reservas do 101 não mudaram
  ok: sessão inexistente recebe 404
Passo 10
  ok: passo 10: resposta sem RSV-4821 nem 302 isolado
  ok: 101 não tem salão em 2030-03-16
  ok: eventos sem RSV-4821
Passo 11
  ok: pendência com nome e data
  ok: ainda não autorizada
  ok: Joana autorizada
Passo 12
  resposta: A piscina funciona das 9h às 20h aos domingos (Art. 22, II do regulamento interno).
  ok: horário de fechamento (20h)
  ok: eventos incluem chamadas de tool dos passos anteriores
  ok: eventos sem trechos de outros capítulos do regulamento
  eventos de S1: 45
Passo 13: reinicie a API (Ctrl+C e suba de novo, sem restaurar) e pressione Enter.

  ok: mesma quantidade de eventos após reinício
  ok: eventos aumentaram
  ok: reservas do 101
  ok: códigos novos e distintos
  ok: 302 continua com RSV-4821
  ok: Joana Ribeiro continua autorizada
Passo 14
  ok: S3 com confirmação pendente
  ok: S4 com confirmação pendente
  ok: aprovação de S3 responde 200
  ok: aprovação de S4 responde 200
  ok: exatamente uma reserva do salão em 2030-05-11 entre 101 e 201

Falhas: 0
```
