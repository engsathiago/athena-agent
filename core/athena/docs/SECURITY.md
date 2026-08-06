# Autorização da Athena

A política principal fica em `~/.athena/security.yaml`.

Uma instalação nova começa sem regras próprias da Athena: modo
`unrestricted`, lista `rules` vazia e auditoria desativada. O arquivo
`~/.athena/SOUL.md` também começa vazio. Até o proprietário escrever suas
regras, aplicam-se apenas as políticas da LLM/provedor e limites técnicos do
sistema operacional ou das ferramentas externas.

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
skills, tarefas, controle visual e ações externas sem confirmação da Athena.
A autenticação do remetente continua separada; ela determina quem é o dono e
não é uma política de conteúdo. Esse modo não transforma automaticamente um
bot privado em público.

### `core`

Delega decisões de autorização à política defensiva do núcleo.

## Comandos

```bash
athena security status
athena security mode controlled
athena security mode unrestricted
athena security mode core
```

Mudanças preservam as regras que o proprietário vier a criar. Reinicie
gateways em execução após alterar o modo. A auditoria começa desativada e pode
ser habilitada manualmente em `security.yaml`.
