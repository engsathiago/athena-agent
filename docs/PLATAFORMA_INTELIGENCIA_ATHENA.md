# Plataforma de Inteligência Athena

Estas capacidades são locais por padrão e não alteram políticas do agente.

## Trace Studio

Registra a linha do tempo de cada execução: modelo, ferramentas, subagentes,
seleção de contexto, tempo, tokens, cache, tentativas e erros. Segredos comuns
são removidos antes da gravação.

```bash
athena traces status
athena traces list
athena traces show tr_ID
athena traces replay tr_ID
athena traces prune --days 30 --keep 5000       # apenas mostra a limpeza
athena traces prune --days 30 --keep 5000 --execute
```

Os dados ficam em `~/.athena/operations/athena-operations.db`.

## Evals 2.0

Além da resposta, os testes verificam trajetória, ferramentas, modelo,
provedor, custo, duração, artefatos e estado final.

```bash
athena evals import-traces --name regressao-real
athena evals ci regressao-real --min-score 0.90
```

Verificações: `tool_called`, `tool_not_called`, `max_tool_calls`,
`min_tool_calls`, `model_is`, `provider_is`, `max_latency_seconds`,
`max_cost_usd`, `trace_status` e `artifact_exists`.

## Athena Flows

Fluxos YAML têm dependências, condições, paralelismo, repetição, checkpoint,
pausa, retomada e bifurcação.

```bash
athena flows init meu-fluxo.yaml
athena flows install meu-fluxo.yaml
athena flows start nome-do-fluxo --input '{"tema":"Athena"}'
athena flows resume fr_ID --value '"aprovado"'
athena flows retry fr_ID etapa
athena flows fork fr_ID etapa
```

Tipos de etapa: `athena`, `command`, `value` e `wait`. Variáveis usam
`{{input.campo}}` e `{{steps.etapa.output.campo}}`.

## Central de Resultados

Execuções e tarefas Kanban entram em uma caixa de revisão. Arquivos são
preservados com hash e histórico de versões.

```bash
athena results status
athena results list
athena results approve result_ID
athena results changes result_ID --note "Ajustar o resumo"
athena results add-artifact result_ID arquivo.pdf
```

## Roteamento Adaptativo

Compara qualidade, sucesso, ferramentas, velocidade e custo. O modelo nunca é
trocado no meio de uma sessão. Configure candidatos em `config.yaml`:

```yaml
smart_model_routing:
  enabled: true
  candidates:
    - model: modelo-local
      provider: ollama
      tasks: [general]
      expected_latency: 2
    - model: modelo-forte
      provider: openrouter
      tasks: [coding, research]
```

O automático vale para novas conversas tanto no terminal quanto no gateway
(incluindo Telegram) e aplica candidatos do mesmo provedor. Decisões entre provedores
ficam visíveis para escolha explícita, evitando trocar credenciais ou protocolo
silenciosamente.

```bash
athena router status
athena router recommend "corrija este projeto" --model modelo-atual
```

## Experimentos Canário

Compara a versão atual com uma candidata em uma parcela estável das tarefas e
promove ou interrompe a candidata conforme o resultado.

```bash
athena experiments create novo-modelo \
  --kind model-routing --baseline modelo-a --candidate modelo-b --traffic 5
athena experiments start novo-modelo
athena experiments status
```

## Pacotes de Trabalho

Um pacote reúne fluxos, skills e avaliações. A distribuição inclui `research`,
`software`, `operations`, `marketing`, `content` e `support`.

```bash
athena packages list
athena packages install research
```

A instalação copia as skills Athena recomendadas que estiverem disponíveis,
registra os fluxos e adiciona as avaliações do pacote. Se uma instalação falhar,
os arquivos anteriores são restaurados.

## Rede de Trabalhadores

A fila distribuída usa capacidades, prioridade, heartbeat, lease e repetição.

Controlador:

```bash
export ATHENA_WORKER_TOKEN='troque-por-um-segredo-longo'
athena workers serve --bind 0.0.0.0 --port 9121
```

Trabalhador:

```bash
export ATHENA_WORKER_TOKEN='o-mesmo-segredo'
athena workers connect https://controlador.exemplo.com \
  --id gpu-01 --label gpu --capability athena --capability command
```

Enviar trabalho:

```bash
athena workers submit athena '{"prompt":"gere o relatório"}' --require gpu
```

Use TLS por proxy reverso ou VPN quando o controlador atravessar a internet.

## Painel, backup e modo offline

Abra `athena dashboard` e acesse **Intelligence**. A página reúne linha do
tempo, revisão, fluxos, roteador, pacotes e trabalhadores.

O banco operacional está dentro de `ATHENA_HOME` e participa do backup
existente. Trace Studio, fluxos, resultados, experimentos e fila funcionam sem
internet; somente etapas com modelos ou serviços externos precisam de conexão.
