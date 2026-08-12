# Usar a Athena pelo Telegram

## Criar o bot

1. Abra uma conversa com `@BotFather` no Telegram.
2. Envie `/newbot` e escolha nome e usuário.
3. Copie o token fornecido.
4. Descubra seu ID numérico com um bot de identificação confiável ou pelo fluxo
   automático apresentado pela Athena.

Trate o token como uma senha. Se ele vazar, revogue-o imediatamente no BotFather.

## Configurar a Athena

```bash
athena gateway setup
```

Escolha Telegram. O assistente oferece configuração automática ou token manual.
Quando pedir usuários permitidos, informe apenas seu ID numérico. A variável
correspondente é `TELEGRAM_ALLOWED_USERS` e pode aceitar IDs separados por
vírgula.

Não habilite `GATEWAY_ALLOW_ALL_USERS` em uma instalação que tenha terminal ou
acesso a arquivos. Sem lista ou pareamento aprovado, o gateway nega usuários
por padrão.

## Iniciar e testar

```bash
athena gateway install
athena gateway start
athena gateway status
```

Envie uma mensagem privada ao bot. Terminal e Telegram compartilham o mesmo
diretório de estado, mas cada conversa mantém sua própria sessão.

## Administração

```bash
athena gateway status
athena gateway restart
athena gateway stop
athena gateway logs
```

Para aprovar um código de pareamento apresentado por um usuário:

```bash
athena pairing approve telegram CODIGO
```

Aprove somente contas que você reconhece.

## Grupos

Autorizar uma pessoa em `TELEGRAM_ALLOWED_USERS` também permite que ela invoque
o bot em grupos. Para controles específicos existem as listas
`TELEGRAM_GROUP_ALLOWED_USERS` e `TELEGRAM_GROUP_ALLOWED_CHATS`. Autorizar um
chat inteiro permite que todos os seus membros interajam com o agente; faça
isso apenas em grupos confiáveis.

## Diagnóstico

Se o bot não responder:

```bash
athena gateway status
athena gateway logs
athena doctor
```

Confirme se o token continua válido, se seu ID está na lista e se a VPS alcança
`api.telegram.org` por HTTPS.
