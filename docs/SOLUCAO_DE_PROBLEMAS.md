# Solução de problemas

## `athena: command not found`

Reabra o terminal ou execute:

```bash
export PATH="$HOME/.local/bin:$PATH"
athena status
```

## O modelo não responde

```bash
athena model
athena doctor
```

Confira a chave em `~/.athena/.env`, o nome do modelo, créditos e conectividade
da VPS. Não cole a chave em issues ou mensagens.

## Telegram não responde

```bash
athena gateway status
athena gateway logs
```

Confirme o token e `TELEGRAM_ALLOWED_USERS`. O gateway nega por padrão um ID
que não esteja autorizado.

## Serviço não inicia após reiniciar a VPS

```bash
athena gateway install
athena gateway restart
athena gateway status
```

Execute esses comandos com o mesmo usuário que instalou a Athena.

## Instalação interrompida

Entre novamente na pasta clonada e repita:

```bash
./install.sh --yes
```

O instalador usa uma área temporária e preserva o aplicativo anterior. Os dados
de `~/.athena` permanecem separados.

## Relatório de erro

Inclua versão, sistema operacional, comando executado e mensagem de erro.
Remova tokens, endereços privados, conversas, nomes de arquivos pessoais e
qualquer conteúdo de `~/.athena/.env`.
