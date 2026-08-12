# Operação avançada da Athena

Este guia reúne os recursos adicionados para medir qualidade, cuidar da
memória, trabalhar sem internet, recuperar a instalação e evoluir skills sem
perder a versão anterior.

> A política da Athena não faz parte destes recursos. Nenhum dos comandos
> abaixo altera `SOUL.md`, identidade, prompts de política ou regras de uso.

## Painel central

Abra o painel normalmente:

```bash
athena dashboard
```

Na página **System**, o quadro **Athena intelligence** mostra:

- resultado da avaliação mais recente;
- quantidade de memórias ativas e itens que merecem revisão;
- disponibilidade do Ollama e dos modelos locais;
- backup completo mais recente;
- propostas de evolução de skills;
- tarefas recentes concluídas com prova verificável.

Esse quadro é apenas um resumo. Ele não altera a configuração ao ser aberto.

## Avaliações repetíveis

Crie a suíte inicial com 30 situações simples:

```bash
athena evals init
```

Ela fica em `ATHENA_HOME/evals/suites/starter.jsonl` e pode ser adaptada para
as tarefas reais do projeto. Cada linha contém uma pergunta e verificações
objetivas da resposta.

Execute a suíte usando o modelo atualmente configurado:

```bash
athena evals run starter
```

Para reduzir o efeito de respostas ocasionais, repita cada caso:

```bash
athena evals run starter --repetitions 3
```

Os relatórios ficam em `ATHENA_HOME/evals/runs`. Compare uma referência com
um candidato antes de aceitar uma mudança:

```bash
athena evals compare caminho/base.json caminho/candidato.json
```

## Memória organizada

A ferramenta `athena_memory` possui duas ações novas:

- `review`: apenas aponta registros antigos, fracos e muito parecidos;
- `maintain`: começa em simulação e só arquiva quando `dry_run` for `false`.

A manutenção nunca arquiva automaticamente uma memória de origem `owner` ou
`system`. Os demais registros não são apagados: mudam para o estado
`archived`, preservando o histórico para auditoria e recuperação.

Configuração opcional:

```yaml
plugins:
  athena-memory:
    maintenance_stale_after_days: 180
    maintenance_low_confidence: 0.35
```

## Ollama e funcionamento sem internet

Confira a instalação local:

```bash
athena offline status
```

Depois de instalar um modelo no Ollama, ligue a Athena a ele:

```bash
athena offline configure --model qwen3:8b
```

O comando configura o provedor local em
`http://127.0.0.1:11434/v1`. Nenhuma chave externa é necessária.

### Pacote para instalar em uma máquina isolada

Prepare o pacote enquanto a máquina ainda possui internet. Primeiro reúna as
dependências Python compatíveis com o sistema de destino:

```bash
python3 -m pip wheel --wheel-dir /tmp/athena-wheels ./core
```

Depois monte o pacote. A opção `--include-models` copia também o armazenamento
do Ollama e pode consumir muitos gigabytes:

```bash
athena offline prepare \
  --output /tmp/athena-offline \
  --wheelhouse /tmp/athena-wheels \
  --include-ollama \
  --include-models
```

Copie `/tmp/athena-offline` para a máquina isolada e execute:

```bash
cd athena-offline
./install-offline.sh
```

O instalador usa somente os arquivos do pacote. Se o pacote não tiver uma
pasta `wheels`, ele tentará usar as dependências que já existem na máquina e
avisará que o pacote não é totalmente independente.

O executável do Ollama e suas bibliotecas nativas precisam corresponder ao
mesmo sistema e à mesma arquitetura da máquina de destino. O destino também
precisa ter Python 3.11, 3.12 ou 3.13 e, quando aplicável, os drivers da GPU.

## Backup e recuperação

O backup completo existente continua sendo criado assim:

```bash
athena backup
```

Liste os arquivos encontrados:

```bash
athena recovery status
```

Antes de restaurar, valide o ZIP, todos os arquivos e cada banco SQLite:

```bash
athena recovery verify ~/athena-backup-AAAA-MM-DD-HHMMSS.zip
```

Faça uma simulação da restauração:

```bash
athena recovery restore ~/athena-backup-AAAA-MM-DD-HHMMSS.zip
```

Para aplicar de verdade:

```bash
athena recovery restore ~/athena-backup-AAAA-MM-DD-HHMMSS.zip --apply
```

Antes da restauração real, a Athena cria automaticamente um snapshot rápido
do estado atual. Assim existe um ponto de retorno caso o arquivo restaurado
não seja o desejado.

## Evolução controlada de skills

O fluxo de evolução atua somente em skills:

1. criar uma proposta;
2. anexar uma avaliação;
3. ativar apenas se a avaliação for aceita;
4. retornar à versão anterior quando necessário.

Veja primeiro os sinais recentes de falha em avaliações e tarefas:

```bash
athena evolve signals
```

Esse comando apenas observa e agrupa problemas. Ele não escreve uma solução
nem altera a Athena sozinho.

Exemplo:

```bash
athena evolve propose ./minha-skill --name minha-skill --reason "melhorar relatórios"
athena evolve evaluate ID_DA_PROPOSTA caminho/relatorio.json
athena evolve activate ID_DA_PROPOSTA
athena evolve rollback ID_DA_PROPOSTA
```

Ao ativar, a versão anterior da skill é guardada junto da proposta. O comando
de retorno restaura essa cópia. Se a skill for modificada depois da proposta,
a ativação é recusada e uma nova proposta deve ser criada.

Consulte o histórico:

```bash
athena evolve status
```

## Sequência recomendada

Para testar uma melhoria com baixo risco:

1. faça `athena backup`;
2. rode uma avaliação de referência;
3. crie a proposta da skill;
4. rode novamente a avaliação;
5. compare os relatórios;
6. anexe o relatório aceito à proposta;
7. ative a skill;
8. acompanhe o quadro **Athena intelligence**;
9. use `rollback` se o resultado real piorar.
