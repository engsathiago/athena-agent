# Melhorias incorporadas à Athena após o estudo dos projetos EVE

Data da implementação: 11 de agosto de 2026.

Esta entrega não copia a identidade, a interface nem trechos de código dos
projetos estudados. Ela recria, dentro da arquitetura da Athena, quatro ideias
que demonstraram utilidade prática.

## 1. Conclusão apoiada por provas

Ao concluir uma tarefa do quadro, a Athena passa a reunir automaticamente o
último teste ou verificação registrado e os arquivos finais declarados. Também
é possível enviar provas explícitas no campo `evidence`.

A avaliação gravada diferencia:

- `verified`: existe ao menos uma prova bem-sucedida;
- `claimed`: existe apenas uma afirmação de que terminou;
- `failed`: alguma prova apresentada falhou.

Configuração em `config.yaml`:

```yaml
kanban:
  completion_evidence: record  # off | record | require
```

O modo padrão `record` preserva compatibilidade e deixa a auditoria visível. O
modo `require` mantém a tarefa aberta quando só há uma alegação sem prova.

## 2. Reflexão que vira memória útil

A memória persistente recebeu a ação `reflect`. Ela guarda um encerramento
curto e padronizado:

- o que foi entregue;
- qual foi a qualidade observada;
- qual é o próximo passo;
- qual lição vale reaproveitar.

Isso reduz a repetição de erros e evita transformar toda conversa em memória.
A reflexão continua corrigível e apagável pelas funções normais da memória da
Athena.

## 3. Ferramentas adequadas para cada tarefa

Uma tarefa Kanban pode usar `toolsets: ["auto"]` ou, no terminal:

```bash
athena kanban create "Corrigir a API" --assignee dev --toolset auto
```

A escolha ocorre antes do início da conversa do trabalhador. Uma tarefa de
programação recebe arquivos, terminal e execução de código; uma pesquisa recebe
web e navegador; uma tarefa visual pode receber visão e geração de imagem. Se o
assunto não for reconhecido, a Athena mantém todas as capacidades autorizadas
pelo perfil, evitando deixar o trabalhador sem recursos.

Também é possível informar toolsets específicos. A tarefa nunca ganha uma
capacidade que o perfil responsável não possuía.

## 4. Laboratório opcional para modelos locais

O comando `athena model-lab` cobre as partes repetitivas e delicadas do ciclo de
um modelo local:

1. `dataset`: limpa um JSONL, mascara segredos e dados pessoais, remove cópias e
   cria uma versão imutável;
2. `compare`: compara as mesmas métricas no modelo atual e no candidato, bloqueia
   regressões e produz um relatório;
3. `register`: registra o caminho ou nome Ollama do candidato;
4. `activate`: aceita normalmente apenas candidatos aprovados;
5. `rollback`: retorna à versão anterior;
6. `status`: mostra o estado do laboratório.

O treinamento pesado continua opcional e pode ser feito com Ollama, Unsloth,
Axolotl, vLLM ou outro motor. O laboratório não troca silenciosamente o modelo
principal da Athena: ele registra a versão aprovada, e a alteração do provedor
continua sendo uma decisão explícita do responsável.

## Limites mantidos de propósito

- Não foi incorporado um conselho fixo de vários modelos, pois aumenta custo e
  latência e tentaria impor uma política única ao projeto.
- Não foi adotada uma verificação por frases de recusa, pois esse método mede
  palavras e não comportamento real.
- Não foi incluído treinamento GPU obrigatório no núcleo da Athena. Máquinas sem
  GPU continuam leves e plenamente funcionais.
