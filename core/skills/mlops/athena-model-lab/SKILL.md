---
name: athena-model-lab
description: Preparar dados, comparar métricas, registrar candidatos e ativar ou reverter modelos locais com o laboratório da Athena. Usar ao criar datasets JSONL para ajuste fino, avaliar um modelo Ollama/vLLM/llama.cpp contra a versão atual, aprovar uma nova versão ou voltar à anterior.
---

# Laboratório de Modelos Athena

Usar o laboratório como a camada de controle ao redor do treinamento externo. Manter o treinamento no motor escolhido e usar a Athena para higienizar dados, decidir com métricas e controlar versões.

## Fluxo

1. Preparar um JSONL imutável, removendo segredos e dados pessoais e eliminando duplicatas:

   `athena model-lab dataset --input conversas.jsonl --name atendimento`

2. Treinar o modelo com Ollama, Unsloth, Axolotl ou outro motor usando o caminho retornado em `dataset_path`. Não incluir registros rejeitados.

3. Executar o mesmo conjunto de avaliações no modelo atual e no candidato. Salvar cada resultado como um objeto JSON de métricas numéricas onde valores maiores sejam melhores.

4. Comparar os resultados e definir limites importantes:

   `athena model-lab compare --baseline atual.json --candidate novo.json --name athena-local-v2 --require safety=0.90 --max-regression 0.02`

5. Registrar o candidato com o relatório produzido:

   `athena model-lab register athena-local-v2 ollama:athena-v2 --evaluation CAMINHO_DO_RELATORIO`

6. Ativar somente se a decisão for `accept`:

   `athena model-lab activate athena-local-v2`

7. Configurar o provedor local da Athena para usar o `model_ref` aprovado. A ativação do laboratório registra a decisão, mas não troca silenciosamente a configuração principal.

8. Reverter quando a experiência real piorar:

   `athena model-lab rollback`

## Regras de qualidade

- Usar um conjunto de avaliação separado do conjunto de treino.
- Comparar sempre contra a versão atualmente usada.
- Incluir métricas de qualidade, execução correta e segurança relevantes ao caso real.
- Rejeitar regressões acima do limite mesmo quando a média geral melhora.
- Usar `--allow-unverified` apenas em ambiente isolado e declarar que a aprovação foi ignorada.
- Consultar `athena model-lab status` antes de alterar a configuração do provedor local.
