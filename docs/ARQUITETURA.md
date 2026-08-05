# Arquitetura da Athena

```text
Terminal / Telegram / outros canais
                │
                ▼
       identidade e autorização Athena
                │
                ▼
 sessões ─ modelo ─ ferramentas ─ skills ─ plugins
    │                    │
    ├── memória          ├── terminal e arquivos
    ├── agentes          ├── navegador e pesquisa
    ├── heartbeat        └── MCP e serviços externos
    └── tarefas agendadas
```

## Limite do produto

O usuário interage com o comando `athena`, o pacote `athena-agent`, as opções
`ATHENA_*` e o estado em `~/.athena`. O núcleo incorporado é uma implementação
interna da distribuição e não exige outro agente instalado.

## Componentes

- `core/athena`: inicialização, identidade, agentes, bindings, heartbeat e
  autoridade de segurança;
- `core/athena_cli`: comandos, assistentes, serviço, diagnóstico e interface;
- `core/agent`: ciclo de conversa, provedores, contexto, memória e transporte;
- `core/tools`: ferramentas disponíveis ao modelo;
- `core/gateway`: sessões e entrega de mensagens;
- `core/plugins` e `core/skills`: extensões sem aumentar o núcleo central;
- `core/tests`: testes de comportamento e integração.

## Estado

O código instalado fica em `~/.local/share/athena`. Configurações, credenciais,
sessões, memória e logs ficam em `~/.athena`, permitindo atualizar o aplicativo
sem apagar a identidade do agente.

## Memória

A memória local combina arquivos de contexto, SQLite FTS5, similaridade
limitada, importância, confiança e decaimento temporal. Operações de criação,
reforço, correção, substituição e esquecimento geram eventos de auditoria sem
copiar o conteúdo completo para o registro.

## Autonomia

Tarefas `cron` executam ações agendadas. O heartbeat realiza verificações
silenciosas em horários configurados. Ambos respeitam perfil, política de
autorização e destino de entrega.
