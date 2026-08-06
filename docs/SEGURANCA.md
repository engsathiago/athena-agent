# Segurança

A Athena pode executar comandos, acessar arquivos e enviar mensagens. Trate-a
como um usuário real do servidor e conceda somente as permissões necessárias.

## Estado inicial

A Athena não instala uma política de segurança própria. Em uma instalação
nova:

- `~/.athena/SOUL.md` fica vazio;
- `security.yaml` usa `mode: unrestricted` e `rules: []`;
- confirmações e bloqueios próprios da Athena ficam desativados;
- a auditoria de decisões fica desativada.

Enquanto o proprietário não escrever uma política, valem somente as políticas
da LLM/provedor e os limites técnicos do sistema operacional ou de ferramentas
externas. A autenticação do Telegram continua obrigatória para identificar quem
pode controlar o agente; autenticação não é uma regra de conteúdo.

## Modos de autorização

- `controlled`: aplica as regras que o proprietário escrever;
- `core`: delega as decisões à política defensiva do núcleo;
- `unrestricted`: não aplica regras de autorização próprias da Athena.

```bash
athena security status
athena security mode controlled
```

O modo de autorização não substitui a autenticação do remetente. No Telegram,
configure `TELEGRAM_ALLOWED_USERS` ou o pareamento privado.

## Política futura do proprietário

Escreva identidade e instruções gerais em `~/.athena/SOUL.md`. Para regras
técnicas por capacidade, altere `~/.athena/security.yaml`, mude para
`controlled` e adicione regras `allow`, `deny` ou `core`.

## Segredos

Tokens ficam em `~/.athena/.env`. Nunca publique esse arquivo. Logs e sessões
também podem conter dados privados; revise-os antes de compartilhar.

Se desejar registrar decisões, habilite `audit.enabled` em
`~/.athena/security.yaml`.

Para comunicar uma vulnerabilidade do projeto, siga [SECURITY.md](../SECURITY.md).
