# Arquitetura da Athena

## Limite do produto

A Athena é uma distribuição independente. O núcleo incorporado é um detalhe de
implementação; usuários interagem somente com o comando `athena`, o pacote
`athena-agent`, as configurações `ATHENA_*` e o estado em `~/.athena`.

```text
comando / identidade / autorização do proprietário
                         │
                         ▼
sessões, modelos, ferramentas, skills, gateway, cron e TUI
                         │
                         ├── memória Athena
                         ├── agentes isolados
                         ├── bindings determinísticos
                         └── heartbeat silencioso
```

## Estado persistente

`ATHENA_HOME` usa `~/.athena` por padrão e delimita todos os subsistemas
persistentes: configuração, credenciais, sessões, memória, skills, tarefas,
logs, workspaces e perfis.

Agentes nomeados possuem espaço de trabalho, configuração, credenciais,
sessões, skills, tarefas, personalidade e memória independentes.

## Autorização

Quando `ATHENA_RUNTIME=1`, a Athena é a autoridade de autorização:

- `unrestricted`: libera as capacidades conectadas;
- `controlled`: aplica a primeira regra compatível e depois o padrão;
- `core`: delega à política defensiva do núcleo.

Validação de protocolo, integridade do banco, pareamento de chamadas de
ferramenta, limites de repetição e verificações do backend continuam ativas.

## Memória

Registros possuem tipo, escopo, importância, confiança, origem, sessão, datas e
substituição. A recuperação combina FTS5, similaridade limitada, importância,
confiança e decaimento temporal.
