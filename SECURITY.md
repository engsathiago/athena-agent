# Política de segurança

Não abra uma issue pública contendo uma vulnerabilidade explorável, token,
chave de API, conversa ou dados de uma instalação.

Use o recurso privado **Security Advisories** deste repositório:

https://github.com/engsathiago/athena-agent/security/advisories/new

Informe versão, sistema operacional, impacto, passos mínimos de reprodução e,
se possível, uma sugestão de correção. Remova todos os segredos e dados
pessoais.

## Escopo inicial

A versão `0.1.x` é experimental. São especialmente relevantes falhas de:

- autenticação ou autorização de gateways;
- exposição de tokens e credenciais;
- execução de comandos sem consentimento;
- acesso indevido a arquivos;
- isolamento entre agentes e perfis;
- injeção através de mensagens, plugins, skills ou MCP;
- falsificação ou corrupção de memória persistente.

## Responsabilidade do operador

Execute a Athena com usuário sem privilégios administrativos, use allowlists
nos canais, mantenha backups e não exponha painéis locais diretamente à
internet. Consulte [docs/SEGURANCA.md](docs/SEGURANCA.md).
