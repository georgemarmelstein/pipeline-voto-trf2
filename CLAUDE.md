# CLAUDE.md

Este repositório é a distribuição do **/pipeline-voto para o TRF2**: dos autos de um recurso
(apelação, agravo, remessa necessária) ao acórdão minutado (ementa, relatório e voto), auditado e
acompanhado da prancha de conferência humana. É inteligência aumentada: o pipeline minuta, o
magistrado decide.

## Arquitetura: orquestrador cego com injeção de contexto

- O comando `/pipeline-voto` (`.claude/commands/pipeline-voto.md`) é o orquestrador. Ele calcula
  `$NUMERO`, `$WORKSPACE` e os caminhos, despacha os subagentes por **invólucro** (o subagente
  `general-purpose` lê o `.md` do agente) e nunca lê os documentos para validá-los.
- A validação é **por script**: `scripts/verificar_voto.py` (gate e retomada; a linha `PENDENTES:`
  é o plano), `verificar_minuta_limpa.py`, `verificar_citacoes.py`, `verificar_proveniencia.py`.
- Cada etapa grava em arquivo e o subagente responde UMA linha de status.

## Regime de modelos

O modelo é **parâmetro da Task**, nunca prosa: no despacho por invólucro o `model:` do frontmatter
do agente não é lido. Extração e coleta em `sonnet`; raciocínio em `sonnet` por padrão e `opus` com
a flag `--opus`.

## Regras invioláveis

1. Nenhuma citação sem verificação: precedente só entra no voto se estiver em `$NUMERO-citaveis.json`
   com lastro no `$NUMERO-fontes.json`.
2. Nenhuma afirmação sem referência: fato dos autos exige página, id ou evento.
3. Nenhum capítulo sem decisão, e nenhum capítulo além do devolvido (skill
   `disciplina-devolutividade-recursal`).
4. Regime de dois tempos: nas fases internas (pesquisa, análise) vale o verbatim com custódia; no
   acórdão vale a minuta limpa (sem aspas de fonte, sem markdown, referências só aos citáveis).
5. Fonte do TRF2 (`trf2-eproc`) não tem adaptador de proveniência: sai como `SEM_ADAPTADOR` e vai
   para a prancha de conferência humana. Nunca tratá-la como confirmada.

## Vozes

- A análise segue o método Marmelstein (o `analisador-recursal` lê a voz em
  `.claude/agents/analise/analisador-marmelstein.md`).
- O voto segue a voz do `fundamentador-marmelstein`.
- A ementa segue o padrão estruturado do CNJ
  (`.claude/skills/perfis-tribunais-federais/references/formato-ementa.md`).

## Dados

Tudo o que o pipeline gera nasce em `data/voto/<numero>/`, que é **gitignored**. Autos, minutas e
pesquisas de processos reais nunca são versionados.

## Convenções

Documentação em português com acentos; código em inglês; pastas em kebab-case; arquivos Python em
snake_case; artefatos `<numero>-<tipo>.md`.
