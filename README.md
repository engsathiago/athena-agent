# Athena Agent

Agente pessoal de IA independente para terminal e plataformas de mensagens.
A Athena conversa, executa ferramentas no computador, mantém sessões e memória
persistentes, cria agentes isolados e pode permanecer ativa em uma VPS por meio
de um serviço do sistema.

> **Versão atual:** `0.3.0` — plataforma operacional completa para testes em
> VPS. Mantenha cópias de segurança dos dados importantes.

## Principais recursos

- interface conversacional no terminal pelo comando `athena`;
- Telegram e outros canais através do gateway de mensagens;
- suporte a Ollama Cloud, OpenAI, Anthropic, OpenRouter e endpoints compatíveis;
- execução de terminal, arquivos, navegador, pesquisa, MCP, plugins e skills;
- memória local persistente e provedores externos opcionais;
- agentes com identidade, espaço de trabalho, sessões e memória separados;
- tarefas agendadas, heartbeat e funcionamento contínuo em Linux;
- conclusão de tarefas com provas, seleção automática de ferramentas e
  laboratório opcional para avaliar modelos locais;
- rastreamento completo, testes de trajetória, fluxos retomáveis e central de
  resultados com artefatos versionados;
- roteamento adaptativo de modelos, experimentos canário, pacotes profissionais
  e trabalhadores distribuídos entre VPSs;
- espaço próprio para o proprietário escrever sua política, sem regras padrão
  impostas pela Athena.

## Instalação rápida no Linux ou macOS

Requisitos: Git, `curl` e uma conta em pelo menos um provedor de modelo. O
instalador cria um Python privado para a Athena; não é necessário instalar
outro agente antes.

```bash
git clone https://github.com/engsathiago/athena-agent.git
cd athena-agent
chmod +x install.sh
./install.sh --setup
```

Reabra o terminal ou execute `source ~/.profile` e inicie:

```bash
athena
```

O programa é instalado em `~/.local/share/athena`, o comando global fica em
`~/.local/bin/athena` e os dados persistentes ficam em `~/.athena`.

## Instalação em uma VPS com Telegram

Em Ubuntu ou Debian:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
git clone https://github.com/engsathiago/athena-agent.git
cd athena-agent
./install.sh --setup
exec "$SHELL" -l
```

Depois configure somente sua conta do Telegram e instale o serviço:

```bash
athena gateway setup
athena gateway install
athena gateway start
athena gateway status
```

O assistente pede o token criado no BotFather e seu ID numérico. Não habilite
acesso público em um bot que possui ferramentas de terminal. Consulte o
[guia completo de VPS](docs/INSTALACAO_VPS.md) e o
[guia do Telegram](docs/TELEGRAM.md).

## Ollama Cloud

Execute:

```bash
athena model
```

Selecione **Ollama Cloud**, informe sua `OLLAMA_API_KEY` e escolha um modelo com
suporte a ferramentas. A inferência acontece na nuvem da Ollama, enquanto as
ferramentas são executadas na máquina onde a Athena está instalada.

## Comandos úteis

```bash
athena                         # abre a conversa no terminal
athena setup                   # configuração geral
athena model                   # provedor e modelo
athena status                  # diagnóstico resumido
athena doctor                  # diagnóstico detalhado
athena memory status           # estado da memória
athena profile list            # perfis isolados disponíveis
athena security status         # política de autorização
athena gateway status          # serviço de mensagens
athena model-lab status        # candidatos de modelos locais avaliados
athena traces status           # rastreamento completo das execuções
athena results status          # entregas aguardando revisão
athena flows status            # fluxos duráveis e retomáveis
athena packages list           # pacotes profissionais disponíveis
athena workers status          # rede de trabalhadores e filas
```

## Dados persistentes

Todo o estado do usuário fica separado do código:

```text
~/.athena/
├── config.yaml
├── .env
├── security.yaml
├── SOUL.md
├── HEARTBEAT.md
├── memories/
├── model-lab/
├── operations/
├── packages/
├── results/
├── profiles/
├── sessions/
├── skills/
├── cron/
└── logs/
```

Nunca publique `~/.athena/.env`: ele pode conter tokens e chaves de API.

## Documentação

- [Operação avançada: avaliações, memória, Ollama offline, recuperação e evolução](docs/OPERACAO_AVANCADA_ATHENA.md)
- [Plataforma de inteligência: traces, fluxos, revisão, roteamento e múltiplas VPSs](docs/PLATAFORMA_INTELIGENCIA_ATHENA.md)
- [Instalação em VPS](docs/INSTALACAO_VPS.md)
- [Configuração de modelos](docs/MODELOS.md)
- [Telegram](docs/TELEGRAM.md)
- [Memória persistente](docs/MEMORIA.md)
- [Segurança](docs/SEGURANCA.md)
- [Arquitetura](docs/ARQUITETURA.md)
- [Melhorias inspiradas pelo estudo dos projetos EVE](docs/MELHORIAS_EVE_ATHENA_2026.md)
- [Solução de problemas](docs/SOLUCAO_DE_PROBLEMAS.md)
- [Como contribuir](CONTRIBUTING.md)
- [Política de segurança](SECURITY.md)

## Atualização

Na pasta clonada:

```bash
git pull --ff-only
./install.sh --yes
```

O instalador preserva os dados de `~/.athena` e guarda a cópia anterior do
aplicativo antes de substituir os arquivos.

## Licença e procedência

Athena é distribuída sob a licença MIT. O projeto contém trabalho de terceiros
modificado e mantém as atribuições obrigatórias em
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). A identidade, a distribuição
e o suporte deste repositório pertencem ao projeto Athena.
