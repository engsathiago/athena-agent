# Instalação da Athena em uma VPS

Este guia usa Ubuntu ou Debian com `systemd`. Para o primeiro teste, use uma
VPS exclusiva com pelo menos 2 GB de RAM, 2 vCPUs e 10 GB livres.

## 1. Preparar o servidor

Entre por SSH com um usuário normal que tenha acesso a `sudo`:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git curl ca-certificates
```

A Athena não deve ser executada como `root`. O serviço terá as mesmas
permissões do usuário que realizou a instalação.

## 2. Baixar e instalar

```bash
git clone https://github.com/engsathiago/athena-agent.git
cd athena-agent
chmod +x install.sh
./install.sh --setup
```

O instalador baixa um Python compatível, cria um ambiente privado e registra o
comando em `~/.local/bin/athena`. Recarregue a sessão:

```bash
exec "$SHELL" -l
athena status
```

## 3. Configurar o modelo

O assistente aberto por `--setup` permite escolher o provedor. Para alterar
depois:

```bash
athena model
```

Para Ollama Cloud, escolha essa opção, informe sua chave e selecione um modelo
com ferramentas. Veja [MODELOS.md](MODELOS.md).

## 4. Testar no terminal

```bash
athena
```

Peça uma resposta simples e depois teste uma ação inofensiva, como listar os
arquivos da pasta atual. Saia com `/exit`.

## 5. Configurar Telegram

Antes de expor o gateway, ative a política controlada:

```bash
athena security mode controlled
athena gateway setup
```

No assistente, escolha Telegram, informe o token do BotFather e adicione
somente seu ID numérico à lista permitida. Não escolha acesso aberto.

## 6. Instalar o serviço contínuo

```bash
athena gateway install
athena gateway start
athena gateway status
```

O serviço é iniciado automaticamente após reinicializações do Linux. Para
acompanhar problemas:

```bash
athena gateway logs
athena doctor
```

O Telegram normalmente usa conexão de saída; não é necessário abrir uma porta
pública para o modo padrão. Mantenha apenas o SSH necessário e siga as regras
do seu provedor de VPS.

## Atualizar

```bash
cd ~/athena-agent
git pull --ff-only
./install.sh --yes
athena gateway restart
```

Se o repositório foi clonado em outro local, use essa pasta. Os dados de
`~/.athena` não são apagados pela atualização.

## Cópia de segurança

Pare o gateway antes de copiar o estado:

```bash
athena gateway stop
tar -czf athena-backup.tar.gz -C "$HOME" .athena
athena gateway start
```

O arquivo de backup contém credenciais. Guarde-o de forma privada e criptografada.
