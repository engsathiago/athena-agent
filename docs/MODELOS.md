# Configuração de modelos

A Athena separa o provedor de inferência das ferramentas executadas no host.
Isso permite usar um modelo em nuvem e ainda operar arquivos, terminal e
navegador na VPS.

## Assistente de configuração

```bash
athena model
```

Escolha o provedor, autentique quando solicitado e selecione um modelo capaz de
usar ferramentas. Depois confirme com:

```bash
athena status
athena
```

## Ollama Cloud

1. Crie uma chave na sua conta Ollama.
2. Execute `athena model`.
3. Escolha **Ollama Cloud**.
4. Informe `OLLAMA_API_KEY` quando solicitado.
5. Selecione um modelo indicado para ferramentas.

O endpoint padrão é `https://ollama.com/v1`. O catálogo é consultado e mantido
em cache local. Preços, limites e disponibilidade são definidos pela Ollama.

## Endpoint compatível com OpenAI

Para um servidor próprio, Ollama local, vLLM ou outro serviço compatível,
escolha o provedor personalizado e informe:

- endereço-base da API;
- nome exato do modelo;
- chave, quando exigida pelo servidor.

Em uma VPS, `localhost` aponta para a própria VPS. Para alcançar outro servidor
na rede, use um endereço privado e restrinja o acesso com firewall.

## Proteção das chaves

As credenciais ficam em `~/.athena/.env`, com permissões privadas. Nunca copie
esse arquivo para o repositório, para mensagens do Telegram ou para relatórios
públicos de erro.
