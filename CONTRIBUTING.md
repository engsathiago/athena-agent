# Contribuindo com a Athena

Obrigado por ajudar o projeto. Correções, testes, documentação em português,
novos provedores e integrações nas bordas do sistema são bem-vindos.

## Ambiente de desenvolvimento

```bash
git clone https://github.com/engsathiago/athena-agent.git
cd athena-agent
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --project core --locked --extra dev
```

Execute os testes principais:

```bash
uv run --project core pytest core/tests/athena core/tests/skills/test_openclaw_migration_hardening.py
```

## Diretrizes

- mantenha a identidade pública, comandos e caminhos com o nome Athena;
- não inclua chaves, tokens, sessões, bancos locais ou arquivos `.env`;
- adicione testes para mudanças de comportamento;
- prefira plugins e skills para capacidades especializadas;
- preserve compatibilidade de memória, sessões e configuração;
- escreva documentação pública em português claro;
- mantenha atribuições e licenças de terceiros.

Abra uma issue antes de alterações arquiteturais grandes. Pull requests devem
explicar o problema, a solução, riscos e os testes realizados.
