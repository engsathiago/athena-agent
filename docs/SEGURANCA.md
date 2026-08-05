# Segurança

A Athena pode executar comandos, acessar arquivos e enviar mensagens. Trate-a
como um usuário real do servidor e conceda somente as permissões necessárias.

## Modos de autorização

- `controlled`: aplica as regras do proprietário; recomendado para VPS e bots;
- `core`: delega as decisões à política defensiva do núcleo;
- `unrestricted`: libera capacidades amplas e deve ser usado somente em
  ambiente isolado e confiável.

```bash
athena security status
athena security mode controlled
```

O modo de autorização não substitui a autenticação do remetente. No Telegram,
configure `TELEGRAM_ALLOWED_USERS` ou o pareamento privado.

## Recomendações para VPS

- não execute como `root`;
- use um usuário dedicado quando possível;
- mantenha SSH por chave e desabilite senhas fracas;
- não exponha o painel web diretamente à internet;
- não habilite acesso público ao gateway;
- mantenha o sistema atualizado;
- faça backup criptografado de `~/.athena`;
- revise plugins e skills antes de instalar;
- use contêiner ou máquina separada para tarefas de alto risco.

## Segredos

Tokens ficam em `~/.athena/.env`. Nunca publique esse arquivo. Logs e sessões
também podem conter dados privados; revise-os antes de compartilhar.

Decisões da política são registradas em
`~/.athena/logs/security-decisions.jsonl`, com alvos protegidos por hash por
padrão.

Para comunicar uma vulnerabilidade do projeto, siga [SECURITY.md](../SECURITY.md).
