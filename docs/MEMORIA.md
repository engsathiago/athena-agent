# Memória persistente

A memória integrada da Athena permanece ativa mesmo sem serviço externo. Ela
usa arquivos de contexto e um banco SQLite pesquisável dentro de `~/.athena`.

São armazenadas informações úteis entre sessões, como preferências, decisões,
projetos e fatos confirmados. As memórias possuem origem, confiança,
importância, data e possibilidade de correção ou substituição.

## Estado

```bash
athena memory status
athena doctor
```

Dentro de uma conversa, `/memory` mostra gravações pendentes e os controles de
aprovação disponíveis.

## Isolamento por agente

Agentes nomeados possuem espaço de trabalho, sessões, skills, tarefas e memória
separados. Isso evita misturar o contexto de projetos diferentes.

```bash
athena agent list
```

## Provedores externos

Provedores como Honcho, Mem0 e outros plugins são opcionais:

```bash
athena memory setup
```

Ativar um provedor externo pode enviar memórias ao serviço escolhido. Leia a
política de privacidade do fornecedor antes de habilitá-lo.

## Backup e exclusão

O diretório completo `~/.athena` deve fazer parte da estratégia de backup. Para
apagar a memória integrada de forma intencional, use o comando de redefinição
apresentado em `athena memory --help` e confira a lista mostrada antes de
confirmar. A exclusão não pode ser desfeita sem backup.
