# Núcleo da Athena Agent

Este diretório contém o núcleo incorporado da distribuição Athena. Para
instalar, operar e contribuir, use a documentação na raiz do repositório:

- [apresentação e instalação](../README.md);
- [instalação em VPS](../docs/INSTALACAO_VPS.md);
- [Telegram](../docs/TELEGRAM.md);
- [modelos](../docs/MODELOS.md);
- [memória persistente](../docs/MEMORIA.md);
- [segurança](../docs/SEGURANCA.md);
- [arquitetura](../docs/ARQUITETURA.md).

O pacote Python é `athena-agent`, o ponto de entrada é `athena` e todo estado
persistente do usuário fica em `~/.athena` ou no caminho definido por
`ATHENA_HOME`.

## Desenvolvimento

Na raiz do repositório:

```bash
uv sync --project core --locked --extra dev
uv run --project core pytest core/tests/athena
```

O núcleo contém componentes modificados sob licença MIT. Consulte
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) para as atribuições legais.
