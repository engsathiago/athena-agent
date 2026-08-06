# Histórico de versões

## 0.2.0 — 2026-08-05

- remove a política de segurança textual padrão da Athena;
- deixa `SOUL.md` vazio para receber exclusivamente regras escritas pelo dono;
- inicia sem regras de autorização e sem auditoria de decisões;
- faz o modo `unrestricted` prevalecer também no controle visual;
- mantém somente autenticação de remetentes, limites técnicos do sistema e as
  políticas próprias da LLM/provedor.

## 0.1.3 — 2026-08-05

- torna a política padrão da Athena controlada pelo proprietário, sem
  confirmações ou recusas genéricas impostas pelo núcleo.

## 0.1.2 — 2026-08-05

- alinha a versão exibida pelo terminal à versão publicada do pacote.

## 0.1.1 — 2026-08-05

- corrige a instalação do runtime Python em instalações novas: a saída do
  instalador do runtime não é mais confundida com o caminho do executável.

## 0.1.0 — 2026-08-05

- primeira distribuição pública independente da Athena;
- comando global `athena` e instalador próprio;
- interface conversacional de terminal;
- gateway contínuo para Telegram e outros canais;
- suporte a Ollama Cloud e múltiplos provedores;
- agentes isolados, bindings, heartbeat e tarefas agendadas;
- memória persistente local com procedência e auditoria;
- autoridade de segurança com modos `unrestricted`, `controlled` e `core`;
- documentação inicial em português para instalação e operação em VPS.
