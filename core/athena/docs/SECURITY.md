# Autorização da Athena

A política principal fica em `~/.athena/security.yaml`.

## Modos

### `controlled`

Recomendado para VPS e mensageria. A primeira regra compatível decide; o efeito
pode ser `allow`, `deny` ou `core`.

```yaml
version: 1
mode: controlled
default: allow
rules:
  - id: proprietario-telegram
    effect: allow
    capability: gateway.receive
    target: "telegram:123456789"
  - id: bloquear-outros
    effect: deny
    capability: gateway.receive
    target: "*"
```

### `unrestricted`

Libera execução, arquivos protegidos, credenciais, rede privada, plugins,
skills, tarefas e ações externas. A autenticação do remetente continua
separada; esse modo não transforma automaticamente um bot privado em público.

### `core`

Delega decisões de autorização à política defensiva do núcleo.

## Comandos

```bash
athena security status
athena security mode controlled
athena security mode unrestricted
athena security mode core
```

Mudanças preservam as regras. Reinicie gateways em execução após alterar o
modo. Decisões são registradas em
`~/.athena/logs/security-decisions.jsonl`, com os alvos protegidos por hash por
padrão.
