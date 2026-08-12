# Primeira camada de produto da Athena

A versão 0.4.0 transforma capacidades que já existiam no núcleo em quatro
áreas visuais e operáveis. Para usá-las, execute `athena dashboard` e abra as
novas opções do menu lateral.

## Central de Missão

A Central de Missão mostra o trabalho dos agentes em colunas: triagem,
planejado, pronto, executando, pausado, revisão e concluído.

Nela é possível:

- criar uma missão e indicar um agente responsável;
- acompanhar o agente e sua última execução;
- enviar novas instruções sem perder o histórico;
- pausar, retomar ou tentar novamente;
- transferir a atividade para outro agente;
- trocar de projeto Kanban e acompanhar trabalhadores de outras VPSs.

As missões usam o mesmo Kanban, perfis, subagentes, provas de conclusão e rede
de trabalhadores já utilizados pelo terminal. Portanto, uma tarefa criada no
painel também aparece nas outras interfaces da Athena.

## Athena Environments

Athena Environments cria computadores Docker separados para trabalhos que não
devem ocorrer diretamente na VPS principal.

Ao criar um ambiente, escolha:

- duração antes da expiração;
- quantidade de memória e processador;
- se os arquivos devem permanecer depois da parada;
- se o ambiente poderá acessar a internet;
- a imagem Docker usada como base.

É possível parar, iniciar, gerar um snapshot e remover cada ambiente. Por
padrão, a internet fica desativada e o ambiente é descartável. Modal Cloud e
Vercel Sandbox continuam disponíveis como backends automáticos de sessões; o
painel gerencia diretamente o Docker local ou da VPS nesta primeira versão.

Para usar esse recurso, o Docker precisa estar instalado e ativo na máquina.
Os limites gerais podem ser ajustados em `~/.athena/config.yaml`:

```yaml
environments:
  max_running: 8
  max_total_cpu: 16
  max_total_memory_mb: 32768
```

## Loja de Integrações

A Loja de Integrações oferece uma visão única de:

- ferramentas MCP disponíveis e instaladas;
- plugins da Athena;
- Telegram e os demais canais de comunicação.

Busca, filtros e estados deixam claro o que está disponível, configurado ou
ativo. O botão de cada item abre o instalador completo correspondente, que
continua responsável por credenciais, OAuth, testes e ativação. Assim, a loja
não cria um segundo sistema de plugins: ela organiza os sistemas existentes.

## Athena Studio

O Studio é o espaço de trabalho para as entregas produzidas pela Athena. Ele
cria modelos iniciais para:

- documentos em Markdown;
- apresentações em HTML;
- planilhas CSV;
- sites HTML;
- diagramas SVG;
- notas de texto.

Também aceita arquivos importados de até 100 MB. Formatos de texto podem ser
editados no navegador. HTML, Markdown, CSV, imagens, SVG, PDF, áudio e vídeo
possuem visualização adequada ao formato.

Cada salvamento que altera o conteúdo cria uma nova versão e preserva a
anterior. O botão **Publicar** envia uma cópia para a Central de Resultados,
onde ela pode ser aprovada, receber pedidos de ajuste e ser baixada como parte
do histórico operacional.

## Onde os dados ficam

Tudo continua dentro do diretório persistente da Athena:

```text
~/.athena/
├── kanban/                 # missões e histórico dos agentes
├── platform/sandboxes/     # registro e áreas persistentes dos ambientes
├── studio/                 # arquivos e versões do Studio
├── results/                # publicações e revisões
└── operations/             # traces, filas, fluxos e trabalhadores
```

Esses dados participam do backup normal da Athena. Ambientes descartáveis não
preservam o sistema de arquivos interno depois que o contêiner é removido;
para guardar algo, ative **Guardar arquivos** ou publique a entrega no Studio.
