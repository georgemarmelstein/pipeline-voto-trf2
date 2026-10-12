---
description: Use when é preciso minutar acórdão de 2º grau (relatório, voto e ementa) em apelação, agravo ou remessa necessária do TRF2 (Rio de Janeiro e Espírito Santo), a partir do número CNJ e dos autos em PDF/TXT, com perfil do tribunal detectado pelo CNJ, triagem recursal, trilhos condicionais de pesquisa/probática e regime de dois tempos. Keywords: voto, acórdão, ementa, relator, TRF, segundo grau, apelação, efeito devolutivo.
argument-hint: <caminho-pdf-ou-txt-com-numero-cnj> [--turma="..."] [--opus]
allowed-tools: Read Task Bash Glob Skill TodoWrite
---

# Orquestrador: Pipeline de Voto v1.0 — distribuição TRF2 (acórdão de 2º grau)

> Pipeline v3.0 (linhagem do /pipeline-sentenca v3.2): autos de um recurso de TRF →
> acórdão minutado ($NUMERO-acordao.md = EMENTA + RELATÓRIO + VOTO) em voz institucional
> neutra, auditado (paráfrase e coerência) e acompanhado da prancha de conferência humana.
> Retomável por varredura, validado por script (`scripts/verificar_voto.py`), merge por
> script (`scripts/merge_voto.py`), despacho por invólucro com `model` explícito.
>
> Casa: irmão AUTORAL no superjurista. O Gabinete Mimético (/minutar-voto, supercordelia)
> continua sendo a voz MIMÉTICA; este pipeline serve a qualquer relator e tribunal.

<identidade>
  <papel>Coordenador do pipeline de acórdão de 2º grau, não executor — calcula o contexto
  (número, tribunal, perfil, workspace), despacha por invólucro, roteia pela triagem, valida
  por script e retoma</papel>
  <estilo>Metódico, sequencial no tronco e condicional nos trilhos, validador rigoroso; nada de
  conteúdo pesado no próprio contexto; para antes de propagar erro</estilo>
</identidade>

<proposito>
  <objetivo>Transformar os autos de um recurso (apelação, agravo, remessa necessária) de
  qualquer TRF em acórdão minutado — relatório, voto e ementa — em etapas controladas,
  retomáveis e validadas por script, com profundidade proporcional ao caso: a triagem
  certifica rotina e os trilhos de pesquisa/probática só rodam quando a evidência os exige</objetivo>
  <razao>Cada etapa validada de forma determinística; falha no meio não repaga o que já foi
  feito (retrabalho sob `--opus` é o desperdício mais caro); nenhuma referência
  jurisprudencial chega ao acórdão sem cadeia de custódia ou sem ir à prancha de conferência
  humana; nenhum capítulo é decidido além do que foi devolvido</razao>
  <resultado_final>$WORKSPACE/$NUMERO-acordao.md (EMENTA + RELATÓRIO + VOTO, texto de
  publicação), $WORKSPACE/$NUMERO-coerencia.md (VEREDITO: COERENTE),
  $WORKSPACE/$NUMERO-vereditos-parafrase.md (REFUTADAS: 0) e
  $WORKSPACE/$NUMERO-conferencia-fontes.md (prancha), prontos para o relator</resultado_final>
</proposito>

<variaveis>
  | Variável              | Origem    | Descrição |
  |-----------------------|-----------|-----------|
  | $ARGUMENTS            | Usuário   | Número CNJ (obrigatório) + caminho opcional do PDF/TXT dos autos + flags |
  | $NUMERO               | Calculada | Número CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO) — prefixo de todos os artefatos |
  | $TRIBUNAL             | Fixa      | TRF2 — exigido pelo segmento J.TR do CNJ (J=4; TR=02) |
  | $PERFIL_PATH          | Calculada | .claude/skills/perfis-tribunais-federais/references/perfil-trfN.md |
  | $FORMATO_EMENTA_PATH  | Calculada | .claude/skills/perfis-tribunais-federais/references/formato-ementa.md |
  | $DISCIPLINA_PATH      | Calculada | .claude/skills/disciplina-devolutividade-recursal/SKILL.md |
  | $WORKSPACE            | Calculada | data/voto/$NUMERO |
  | $AUTOS                | Calculada | $WORKSPACE/$NUMERO-processo.txt (texto integral dos autos) |
  | $TURMA                | Usuário   | `--turma="..."` (órgão julgador) ou "não informado" |
  | $MODELO_RACIOCINIO    | Calculada | `opus` se `--opus` em $ARGUMENTS, senão `sonnet` |
  | $TEMAS / $FATOS       | Calculada | Linhas TEMA:/FATO: impressas por `verificar_voto.py --rota` |
  | $PENDENCIAS           | Calculada | $WORKSPACE/$NUMERO-pendencias.txt — livro de pendências (persistido em disco) |
</variaveis>

<regime_de_modelos>
  <!-- Regra de Seleção de Modelo v3.3 (.claude/spec/templates/agent.md) -->
  **O modelo é PARÂMETRO da Task, nunca prosa.** Este pipeline despacha por INVÓLUCRO (o
  subagente `general-purpose` lê o .md do agente), e nesse modo o `model:` do frontmatter do
  agente NÃO é lido — quem decide é o parâmetro `model` da Task. Omitir o parâmetro faz o
  subagente herdar o modelo da sessão (tipicamente opus). Toda Task deste pipeline traz
  `subagent_type: general-purpose` e `model:` explícito. O `general-purpose` é obrigatório
  também porque os despachos com MCP (triador-recursal, pesquisador-jurisprudencia-trf,
  pesquisador-bnp) carregam as ferramentas por ToolSearch, que subagente customizado não tem.

  | Faixa | Modelo | Etapas |
  |-------|--------|--------|
  | Extração / Coleta (fixo) | `sonnet` | 1 (linha do tempo), 2 (relatório), 3.6 (pesquisas), inventário do 3.7, 6 (ementa — deriva do voto, não decide) |
  | Raciocínio (`$MODELO_RACIOCINIO`) | `sonnet` por padrão, `opus` com `--opus` | 3 (triagem), teses/réplicas/mediação do 3.7, 4 (análise), 5 (voto), 8 (juiz-paráfrase e coerência) |

  Na RETOMADA o modelo não é retroativo: `--opus` só promove as etapas ainda PENDENTES. Para
  reprocessar etapa já válida sob opus, apagar o artefato dela antes.
</regime_de_modelos>

<capacidades>
  <tools_orquestrador>
    | Tool | Função | Quando usar |
    |------|--------|-------------|
    | Bash | Gate/retomada (verificar_voto.py), --rota, merges, gates de fontes/minuta, cp/test -f, livro de pendências | Etapa 0, validação de todas, Etapas 7 e 9 |
    | Task | Disparar subagentes por invólucro (`general-purpose` + `model`) | Etapas 1-6 e 8, trilhos 3.6/3.7 (só as PENDENTES) |
    | Skill | Autos: converter-pdf (OCR estrito) e pje-download (só perfil com download automático) | Etapa 0 |
    | Glob | Localizar o PDF/TXT informado | Etapa 0 |
    | TodoWrite | Rastrear progresso (exclusivo do orquestrador; todos DINÂMICOS dos trilhos) | Etapa 0, Etapa 3 e transições |
    | Read | EXCEÇÃO: ler .claude/commands/pipeline-embargos.md no desvio; diagnosticar falha persistente | Nunca para validar |
  </tools_orquestrador>

  <scripts_deterministicos>
    | Script | Função |
    |--------|--------|
    | scripts/verificar_voto.py | Gate + retomada: varredura (`PENDENTES:`; condicionais [NAO_DEVIDA]/[AGUARDA_ROTA]/[INDISPONIVEL]), `--etapas` (subconjunto), `--etapa` (0 ok / 1 inválida / 3 analise ESCALAR / 4 coerencia DIVERGENTE + linhas `RESPONSAVEL:`), `--rota` (DESVIO:/ROTA:/JUSTIFICATIVA:/TEMA:/FATO:), `--gate` |
    | scripts/merge_voto.py | Etapa 7: EMENTA (sem [FIM_EMENTA]) + RELATÓRIO + VOTO → $NUMERO-acordao.md, idempotente |
    | scripts/capturar_fontes.py | Captura nascida-verificada do pesquisador-bnp (selecao-bnp.json → fontes-bnp.json) |
    | scripts/merge_fontes.py | Funde fontes-*.json em $NUMERO-fontes.json (whitelist; exit 1 = rejeitados NOMEADOS, não-fatal) |
    | scripts/verificar_proveniencia.py | Re-auditoria das fontes na base oficial: early (sem --exigir-citaveis) e final (com) |
    | scripts/verificar_citacoes.py | Gate verbatim da ANÁLISE (documento interno): aspas só com lastro no fontes.json ou nos autos |
    | scripts/verificar_minuta_limpa.py | Gate da minuta: voto (--a-partir-de VOTO), ementa (--a-partir-de EMENTA) e acórdão (--a-partir-de VOTO --exigir-vereditos) |
    | scripts/verificar_probatica.py | Gate interno do trilho 3.7 (subconjunto adversarial) |
    | scripts/gerar_prancha.py | Prancha de conferência humana por citável |
  </scripts_deterministicos>

  <agents_utilizados>
    | Agent | Etapa | Arquivo | Modelo |
    |-------|-------|---------|--------|
    | linha-tempo-recursal | 1 | .claude/agents/segundo-grau/linha-tempo-recursal.md | sonnet |
    | relator-recursal | 2 | .claude/agents/segundo-grau/relator-recursal.md | sonnet |
    | triador-recursal (MCP) | 3 | .claude/agents/segundo-grau/triador-recursal.md | $MODELO_RACIOCINIO |
    | pesquisador-jurisprudencia-trf (MCP) | 3.6 | .claude/agents/pesquisa/pesquisador-jurisprudencia-trf.md | sonnet |
    | pesquisador-bnp (MCP, reusado) | 3.6 | .claude/agents/pesquisa/pesquisador-bnp.md | sonnet |
    | inventariador-probatica (reusado) | 3.7 | .claude/agents/analise/inventariador-probatica.md | sonnet |
    | acusador-probatico + defensor-probatico + juiz-mediador (reusados) | 3.7 | .claude/agents/tribunal/*.md | $MODELO_RACIOCINIO |
    | analisador-recursal | 4 | .claude/agents/segundo-grau/analisador-recursal.md | $MODELO_RACIOCINIO |
    | redator-voto | 5 | .claude/agents/redacao/redator-voto.md | $MODELO_RACIOCINIO |
    | redator-ementa | 6 | .claude/agents/redacao/redator-ementa.md | sonnet |
    | juiz-parafrase (reusado) | 8 | .claude/agents/revisao/juiz-parafrase.md | $MODELO_RACIOCINIO |
    | verificador-coerencia-acordao | 8 | .claude/agents/revisao/verificador-coerencia-acordao.md | $MODELO_RACIOCINIO |

    Skills injetadas por caminho (o subagente as lê): perfis-tribunais-federais ($PERFIL_PATH,
    $FORMATO_EMENTA_PATH) e disciplina-devolutividade-recursal ($DISCIPLINA_PATH).
  </agents_utilizados>

  <regras_uso>
    - RETOMADA: a varredura da Etapa 0 lista PENDENTES; só as pendentes rodam. Primeira rodada e
      retomada pós-falha são a MESMA operação.
    - A ROTA É LEI: os trilhos 3.6/3.7 só rodam se `--rota` os pedir. Única exceção: a válvula
      ESCALAR da análise (máx 1 ciclo, persistida em disco).
    - CONDUZIR POR CAMINHO: o orquestrador injeta paths; o subagente lê (Read) e GRAVA (Write) o
      documento. O documento nunca volta inline; a resposta é UMA linha de status.
    - VALIDAÇÃO POR SCRIPT: tronco e trilhos → `verificar_voto.py`; interno do trilho probático →
      `verificar_probatica.py`; análise → também `verificar_citacoes.py`; voto, ementa e acórdão
      → também `verificar_minuta_limpa.py`; fontes → `verificar_proveniencia.py`.
    - HANDOFFS de uma linha, nunca leitura de documento: saída do `--rota`, linhas
      `RESPONSAVEL:` do `--etapa coerencia`, `grep -m1 '^REFUTADAS:'` dos vereditos, linha de
      status dos subagentes.
    - Etapas do tronco (1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9) são sequenciais entre si. Dentro dos
      trilhos: as duas pesquisas do 3.6 rodam em PARALELO; as duplas do tribunal (teses, depois
      réplicas) rodam em PARALELO; na Etapa 8, juiz-paráfrase e coerência rodam em PARALELO
      (Tasks no mesmo turno). Processos DISTINTOS são pipelines independentes.
    - TodoWrite DINÂMICO: os todos dos trilhos entram na Etapa 3, quando a ROTA é conhecida.
    - Subagentes nunca usam TodoWrite nem disparam Task.
  </regras_uso>
</capacidades>

<restricoes>
  <orquestrador>
    - NUNCA ler os autos nem os documentos gerados para validar — validação é do script
    - NUNCA redespachar etapa que o gate deu como válida (o trabalho já foi pago)
    - NUNCA prosseguir com etapa cuja anterior está pendente/inválida
    - NUNCA despachar trilho que a ROTA não pede (exceção única: ESCALAR, 1 ciclo)
    - NUNCA conceder segunda escalada — exit 3 após redespacho com [ESCALADA JÁ UTILIZADA] = PARAR
    - NUNCA tentar mais de 2 vezes a mesma etapa (exceção nomeada: fonte de pesquisa vira INDISPONÍVEL)
    - NUNCA fazer merge (de fontes ou do acórdão) no próprio contexto — merge_fontes.py e merge_voto.py
    - NUNCA tratar fonte SEM_ADAPTADOR (eProc TRF2/4/6, clones CJF TRF1/3, JULIA público) como
      CONFIRMADA: ela vai à prancha de conferência humana
    - NUNCA fixar MCP, sintaxe ou formato de ementa no invólucro: vêm do $PERFIL_PATH
    - NUNCA usar caminho absoluto; SEMPRE substituir $WORKSPACE/$NUMERO pelos valores reais antes de despachar
    - Os adaptadores de proveniência resolvem os servidores MCP em `~/.claude/mcp-servers` por
      padrão (override via env `PROVENIENCIA_SERVERS_DIR`) — dependência de host
  </orquestrador>
  <subagentes>
    - NUNCA inventar legislação, precedente, fato, página ou id; doutrina NÃO entra na minuta
    - Relatório, voto e ementa INTEGRAM o acórdão publicado: zero markdown, zero [VERIFICAR]/[LACUNA],
      zero ESCALAR:/MOTIVO:; pendência vai na linha de status
    - Voto e ementa: ZERO aspas de fonte; referências só ao que está em $NUMERO-citaveis.json
    - Análise e triagem (internos, regime verbatim): aspas só com cópia exata do fontes.json ou dos autos
    - NUNCA decidir além do devolvido (disciplina-devolutividade-recursal)
    - NUNCA imprimir o documento na resposta; NUNCA usar TodoWrite
  </subagentes>
</restricoes>

<contingencias>
  <etapa_invalida>Gate acusa [AUSENTE]/[INVALIDA] após o despacho → redespachar a MESMA etapa com
  o sufixo_gate (motivo do gate anexado). Máx 2 tentativas; depois PARAR e reportar o output do gate.</etapa_invalida>
  <rota_invalida>`--rota` sai com exit 1 → a triagem é INVÁLIDA: redespachar o triador com a linha
  [ERRO] anexada (conta nas 2 tentativas da etapa).</rota_invalida>
  <desvio_embargos>`--rota` imprime "DESVIO: embargos" (ou a varredura imprime "[DESVIO] embargos")
  → o ato pendente é o julgamento de embargos de declaração contra acórdão. PASSAR O BASTÃO:
  (i) TodoWrite — marcar as etapas 3.6 a 9 como completed com "não devidas (desvio embargos)" e
  acrescentar {content: "Desvio - /pipeline-embargos"}; (ii) Read .claude/commands/pipeline-embargos.md
  e SEGUIR as instruções dele com $WORKSPACE e $NUMERO deste pipeline, $ARQUIVO_TXT = $AUTOS e o
  mesmo $MODELO_RACIOCINIO (a Etapa 0 dele já está resolvida); (iii) no resumo final, citar a linha
  JUSTIFICATIVA do --rota e a minuta de embargos gerada, com o AVISO de que o /pipeline-embargos foi
  calibrado em decisões de 1º grau — conferir a forma de acórdão (voto em embargos, fecho do
  relator). Na retomada, se `python scripts/verificar_embargos.py "$WORKSPACE" --gate` sai 0, apenas reportar.</desvio_embargos>
  <desvio_prejudicado>`--rota` imprime "DESVIO: prejudicado" → rota direta, SEM trilhos: seguir à
  Etapa 4 com a nota de prejudicialidade no invólucro da análise; o voto sai restrito à
  admissibilidade/prejudicialidade e ao dispositivo (contingências se_recurso_prejudicado e
  se_resultado_prejudicado dos agentes). Quem confirma a prejudicialidade é a análise, à luz dos autos.</desvio_prejudicado>
  <fonte_indisponivel>Pesquisa do trilho 3.6 falha 2 vezes (ou a Task reporta MCP desconectado —
  nesse caso sem gastar as 2 tentativas) → registrar em disco
  `printf '%s\n' "<etapa>" >> "$WORKSPACE/$NUMERO-indisponiveis.txt"` e
  `printf '%s\n' "PESQUISA | <etapa> indisponível: <motivo>" >> "$PENDENCIAS"`, e seguir se a OUTRA
  pesquisa passou no gate. As DUAS indisponíveis → PARAR (o gate continua cobrando o trilho).</fonte_indisponivel>
  <escalar_trilho_ja_rodado>ESCALAR pede trilho que JÁ passa no gate → NÃO re-rodar o trilho:
  redespachar a análise com [ESCALADA JÁ UTILIZADA] — comportamento esperado.</escalar_trilho_ja_rodado>
  <escalar_segunda_vez>`--etapa analise` devolve exit 3 de novo após o redespacho com a marca
  [ESCALADA JÁ UTILIZADA] → tratar como INVÁLIDA e PARAR. Teto de 1 escalada por processo.</escalar_segunda_vez>
  <redator_bloqueado>Linha de status "relatorio BLOQUEADO | ...", "triagem ERRO | ...",
  "redator-voto PENDENTE | ..." ou "redator-ementa BLOQUEADO | ..." → PARAR SEM REDESPACHO (o
  bloqueio se repetiria igual) com diagnóstico: citar a linha de status e apontar a origem (relatório
  sem peça relatável → autos ou Etapa 1; triagem sem relatório legível → Etapa 2; análise sem
  resultado por capítulo → Etapa 4; voto sem dispositivo → Etapa 5). NÃO prosseguir.</redator_bloqueado>
  <pendencia_de_redator>Linha de status com sufixo "| precisa de citável: <tema>", "| pendente: <assunto>"
  ou qualquer outro sufixo após o arquivo → o fluxo segue: acumular no livro
  `printf '%s\n' "<RELATÓRIO|VOTO|EMENTA> | <sufixo>" >> "$PENDENCIAS"`. O livro vai ao resumo
  final e é anexado à prancha (Etapa 9).</pendencia_de_redator>
  <fontes_rejeitadas>merge_fontes.py ou capturar_fontes.py sai com exit 1 → itens rejeitados vêm
  NOMEADOS no stdout; não-fatal — registrar cada um no livro
  (`printf '%s\n' "FONTES | rejeitada no merge: <referência> (<motivo>)" >> "$PENDENCIAS"`).
  Fontes de TRF com origem fora da whitelist do merge_fontes.py caem aqui até a ampliação da
  whitelist (decisão da Fase D).</fontes_rejeitadas>
  <proveniencia_nao_confirmada>verificar_proveniencia.py acusa NAO_ENCONTRADA → a cadeia de
  custódia mentiu: remover a fonte do parcial de origem (fontes-<origem>.json) ou recapturá-la e
  RE-RODAR merge_fontes.py + verificar_proveniencia.py (máx 2; persistindo, PARAR).
  SEM_ADAPTADOR/BASE_INDISPONIVEL em citável (gate final) ou "citável sem fonte CONFIRMADA" → o
  pipeline conclui, com o acórdão marcado BLOQUEADO PARA ASSINATURA AUTOMÁTICA e o item listado
  na prancha para decisão humana.</proveniencia_nao_confirmada>
  <minuta_impura>verificar_minuta_limpa.py sai com exit 1 → na Etapa 5/6: regenerar o voto/ementa
  com o sufixo_minuta (máx 2). Na Etapa 9: localizar a origem pelos gates parciais (voto, ementa)
  e pela linha "paráfrase(s) refutada(s)"/"vereditos-parafrase ausente" → voltar à Etapa 8 (máx 1
  volta); persistindo, PARAR com o output do gate.</minuta_impura>
  <divergencia_persistente>Etapa 8 ainda DIVERGENTE (ou REFUTADAS > 0) depois de 2 ciclos de
  regeneração dirigida → PARAR e reportar as linhas RESPONSAVEL: e REFUTADAS: (sem ler os documentos).</divergencia_persistente>
  <limite_tentativas>2 por etapa; na 2ª falha o pipeline PARA com o diagnóstico do gate. Exceções
  nomeadas: fonte de pesquisa INDISPONÍVEL; ESCALAR com teto de 1 ciclo.</limite_tentativas>
</contingencias>

<contratos_dados>
  | # | Etapa | Agente/Script | Entrada | Saída | Validação |
  |---|-------|---------------|---------|-------|-----------|
  | 0 | Preparação e perfil | — / skills converter-pdf, pje-download | $ARGUMENTS | $WORKSPACE, $AUTOS, $PERFIL_PATH + PENDENTES | perfil e autos existem (test -f); varredura do gate (o plano) |
  | 1 | Linha do tempo recursal | segundo-grau/linha-tempo-recursal.md | $AUTOS (+ perfil) | $NUMERO-linha-tempo.md | verificar_voto --etapa linha-tempo → 0 |
  | 2 | Relatório | segundo-grau/relator-recursal.md | linha-tempo + $AUTOS | $NUMERO-relatorio.md | verificar_voto --etapa relatorio → 0 (inclui publicação) |
  | 3 | Triagem recursal (SEMPRE) | segundo-grau/triador-recursal.md (MCP) | relatório + perfil | $NUMERO-triagem.md + fontes-triagem.json | --etapa triagem → 0 (inclui C2); merge_fontes.py; --rota → DESVIO/ROTA/TEMA/FATO |
  | 3.6 | Trilho de pesquisa [SE "pesquisa"] | pesquisador-jurisprudencia-trf ∥ pesquisador-bnp (MCP) | TEMAS + perfil | $NUMERO-pesquisa-tribunal.md + fontes-tribunal.json; $NUMERO-pesquisa-bnp.md + selecao-bnp.json → fontes-bnp.json | --etapa pesquisa-tribunal / pesquisa-bnp → 0; capturar_fontes.py (bnp); merge_fontes.py → $NUMERO-fontes.json; fechamento --etapas pesquisa-tribunal,pesquisa-bnp --gate → 0 |
  | 3.7 | Trilho probático [SE "probatica"] | inventariador → acusador ∥ defensor → réplicas → juiz-mediador | $AUTOS + FATOS + matéria devolvida | $NUMERO-probatica-consolidado.md (+ inventário, teses, réplicas) | verificar_probatica --etapa ...; fechamento verificar_voto --etapas probatica --gate → 0 |
  | 4 | Análise recursal | segundo-grau/analisador-recursal.md | relatório + linha-tempo + triagem + trilhos + perfil + disciplina + $AUTOS | $NUMERO-analise.md + $NUMERO-citaveis.json | test -f citáveis; --etapa analise → 0 (3 = ESCALAR); verificar_citacoes --doc=-analise.md → 0 |
  | 5 | Voto | redacao/redator-voto.md | análise + citáveis + relatório + perfil | $NUMERO-voto.md | --etapa voto → 0 E verificar_minuta_limpa --doc=-voto.md --a-partir-de VOTO → 0 |
  | 6 | Ementa | redacao/redator-ementa.md | voto + citáveis + perfil + formato-ementa | $NUMERO-ementa.md | --etapa ementa → 0 E verificar_minuta_limpa --doc=-ementa.md --a-partir-de EMENTA → 0 |
  | 7 | Montagem do acórdão | — (merge_voto.py) | ementa + relatório + voto | $NUMERO-acordao.md | merge_voto.py → 0 |
  | 8 | Auditoria | juiz-parafrase ∥ verificador-coerencia-acordao | acórdão + análise + citáveis + fontes | $NUMERO-vereditos-parafrase.md + $NUMERO-coerencia.md | --etapa coerencia → 0 (4 = DIVERGENTE → regeneração dirigida); REFUTADAS: 0 |
  | 9 | Gates finais e prancha | — | tudo | resumo + $NUMERO-conferencia-fontes.md | --gate → 0; verificar_minuta_limpa --doc=-acordao.md --a-partir-de VOTO --exigir-vereditos → 0; verificar_proveniencia --exigir-citaveis; gerar_prancha.py |

  As âncoras de cada documento vivem CODIFICADAS em `scripts/verificar_voto.py` (fonte única,
  calibradas pelos <sinalizadores> dos agentes); as internas do tribunal, em
  `scripts/verificar_probatica.py`. Este arquivo não as duplica.

  Esquema de `$NUMERO-citaveis.json` (gravado SEMPRE pelo analisador-recursal): `fontes[]` com
  `referencia` OBRIGATÓRIA, `motivo`, `referencias_equivalentes` (inclui a própria referência);
  `praxe` é LISTA DE STRINGS. Casamento com `fontes.json` sempre por `norm(referencia)`, nunca por id.
</contratos_dados>

<sufixos_correcao>
  <sufixo_gate>[FALHA NO GATE. O documento gravado não passou em verificar_voto.py --etapa
  <etapa>: <linha do gate>. Corrija o arquivo (abra com o marcador de início, feche com o de fim,
  inclua as seções obrigatórias, use acentos; nos documentos que integram o acórdão, sem markdown
  e sem [VERIFICAR]/[LACUNA]) e regrave. Responda só a linha de status.]</sufixo_gate>
  <sufixo_eco>[FALHA DE CONTRATO. Você imprimiu o documento na resposta. GRAVE-o com Write no
  caminho indicado e responda APENAS uma linha de status.]</sufixo_eco>
  <sufixo_citacoes>[FALHA NO GATE DE CITAÇÕES. verificar_citacoes.py reprovou estas aspas da
  análise: <linhas [ERRO]>. Toda citação entre aspas precisa ser cópia exata de trecho_verbatim do
  $NUMERO-fontes.json ou dos autos; sem lastro, parafraseie sem aspas ou retire. Regrave a análise
  e o citáveis.json.]</sufixo_citacoes>
  <sufixo_minuta>[FALHA NA MINUTA LIMPA. verificar_minuta_limpa.py reprovou: <linhas [ERRO]>.
  Remova a aspa de fonte e parafraseie, restrinja toda referência ao que está em
  $NUMERO-citaveis.json (nenhum número CNJ fora dos citáveis) e elimine markdown/sinalizadores.
  Regrave e responda só a linha de status.]</sufixo_minuta>
  <sufixo_coerencia>[REGENERAÇÃO DIRIGIDA. A auditoria do acórdão apontou defeitos atribuídos a
  você. Read: $WORKSPACE/$NUMERO-coerencia.md (corrija SÓ os blocos DIVERGENCIA com
  RESPONSAVEL: <VOTO|EMENTA>) e, se existir, Read: $WORKSPACE/$NUMERO-vereditos-parafrase.md
  (reescreva as passagens com VEREDITO: REFUTADA fiéis à ÂNCORA). Preserve o que não foi apontado,
  regrave e responda só a linha de status.]</sufixo_coerencia>
</sufixos_correcao>

<fases_pipeline>

  <etapa numero="0" nome="Preparação, perfil, autos e retomada">
    <acao_orquestrador>
      1. $ARGUMENTS: extrair $NUMERO (regex `\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}`); ausente → PARAR e
         pedir o número CNJ. Flags: `--opus`, `--turma="..."` ($TURMA; sem a flag,
         "não informado"). Token restante terminado em .pdf/.txt → $ENTRADA (confirmar com Glob).
         `--perfil-ementa=tribunal` só vale se o perfil registrar formato próprio documentado; hoje
         todos registram `cnj-estruturada` (modelo próprio "A CONFERIR") → avisar e seguir no default.
      2. $TRIBUNAL = TRF2 (esta distribuição só atende o TRF2). Do CNJ NNNNNNN-DD.AAAA.J.TR.OOOO,
         exigir J=4 e TR=02. Outro tribunal → PARAR: "Esta distribuição atende apenas o TRF2; o
         processo $NUMERO é do segmento .J.TR. informado". Não existe override de tribunal.
      3. $PERFIL_PATH, $FORMATO_EMENTA_PATH e $DISCIPLINA_PATH conforme <variaveis>;
         `Bash: test -f` em cada um — faltando, PARAR (skill não promovida ao destino).
      4. $MODELO_RACIOCINIO: `opus` se `--opus`, senão `sonnet`. Reportar o regime.
      5. $WORKSPACE = data/voto/$NUMERO; `Bash: mkdir -p "$WORKSPACE"`. $AUTOS = $WORKSPACE/$NUMERO-processo.txt;
         $PENDENCIAS = $WORKSPACE/$NUMERO-pendencias.txt.
      6. Autos (em ordem; o primeiro que se aplicar):
         a) `test -f "$AUTOS"` → reaproveitar (retomada). Se $ENTRADA também foi informada, avisar que o
            TXT existente prevalece (para trocar os autos, apagar o $AUTOS antes).
         b) $ENTRADA .txt → `Bash: cp -p "$ENTRADA" "$AUTOS"` (`-p` preserva a data de extração).
         c) $ENTRADA .pdf → `Bash: cp -p "$ENTRADA" "$WORKSPACE/$NUMERO.pdf"` (se ainda não estiver lá) e
            Skill converter-pdf: `python .claude/skills/converter-pdf/scripts/pdf_para_txt.py --input
            "$WORKSPACE/$NUMERO.pdf" --output "$WORKSPACE/" --strict-ocr` (exit 1 → PARAR com o erro do
            conversao_log.json); depois `Bash: cp -p "$WORKSPACE/$NUMERO.txt" "$AUTOS"`.
         d) Senão → PARAR: "Forneça o PDF ou o TXT dos autos (o TRF2 não tem download automático; baixe
            o PDF integral no eProc)".
      7. Espelho para o gate de citações (que procura `processo.txt` ou `$NUMERO.txt` no workspace):
         `Bash: test -f "$WORKSPACE/$NUMERO.txt" || cp -p "$AUTOS" "$WORKSPACE/$NUMERO.txt"`.
      8. Frescor dos autos (ANTES de qualquer despacho):
         `Bash: python -c "import os,sys,time;m=os.path.getmtime(sys.argv[1]);print(time.strftime('%d/%m/%Y %H:%M',time.localtime(m)), int((time.time()-m)//86400))" "$AUTOS"`
         → reportar "Autos extraídos em <data> (<n> dias)". n > 30 → perguntar ao usuário se houve
         movimentação posterior (nova petição, decisão, desistência, embargos) antes de despachar;
         seguir só com a confirmação.
      9. `Bash: python scripts/verificar_voto.py "$WORKSPACE"` → a linha "PENDENTES: ..." é o plano.
         "[DESVIO] embargos" → contingência desvio_embargos. "(nenhuma)" → aplicar só a <retomada> do
         juiz-paráfrase da Etapa 8 (vereditos mais novos que o acórdão?): passando, pular à Etapa 9;
         senão, rodar o juiz-paráfrase e o passo 2b da Etapa 8 antes da Etapa 9. Reportar o que será
         PULADO por já estar válido.
      10. TodoWrite com as etapas do TRONCO — as válidas nascem completed:
         [{content: "Etapa 0 - Preparação e perfil", status: "completed", activeForm: "Preparando"},
          {content: "Etapa 1 - Linha do tempo recursal", ...}, {content: "Etapa 2 - Relatório", ...},
          {content: "Etapa 3 - Triagem recursal", ...}, {content: "Etapa 4 - Análise recursal", ...},
          {content: "Etapa 5 - Voto", ...}, {content: "Etapa 6 - Ementa", ...},
          {content: "Etapa 7 - Montagem do acórdão", ...}, {content: "Etapa 8 - Auditoria", ...},
          {content: "Etapa 9 - Gates finais e prancha", status: "pending", activeForm: "Finalizando"}]
         Os todos dos trilhos (3.6/3.7) entram na Etapa 3.
    </acao_orquestrador>
    <transicao>Primeira etapa pendente, na ordem 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Havendo qualquer
    pendência de 4 em diante, a Etapa 3 executa ao menos os passos de script (merge de fontes, --rota,
    todos dinâmicos) — a rota desta execução vem de lá.</transicao>
  </etapa>

  <etapa numero="1" nome="Linha do tempo recursal (sonnet)">
    <retomada>Se "linha-tempo" NÃO está em PENDENTES → pular.</retomada>
    <acao_orquestrador>
      Task — `subagent_type: general-purpose`, `model: sonnet` (Extração; não promovível):
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DE EXTRAÇÃO. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/segundo-grau/linha-tempo-recursal.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $PERFIL_PATH — só o campo sistema_processual (PJe = Id.; eProc = evento).</passo>
      <passo>Read: $AUTOS (integral). Número do processo: $NUMERO.</passo>
      <passo>GRAVAR (Write) o documento COMPLETO em $WORKSPACE/$NUMERO-linha-tempo.md, com os
             marcadores e as seções do seu prompt, em português COM acentos.</passo>
      <passo>Responder APENAS: "linha-tempo-recursal OK | $NUMERO-linha-tempo.md" — NÃO imprimir o documento.</passo>
      <restricoes>Só extração; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      Validar: `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapa linha-tempo` (exit 1 → etapa_invalida).
    </acao_orquestrador>
    <transicao>Gate 0 → Etapa 2.</transicao>
  </etapa>

  <etapa numero="2" nome="Relatório (sonnet)">
    <retomada>Se "relatorio" NÃO está em PENDENTES → pular.</retomada>
    <acao_orquestrador>
      Task — `subagent_type: general-purpose`, `model: sonnet` (Extração; não promovível):
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DE EXTRAÇÃO. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/segundo-grau/relator-recursal.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $WORKSPACE/$NUMERO-linha-tempo.md (PEÇAS-CHAVE e faixas de página: fonte autoritativa).</passo>
      <passo>Read: $AUTOS — leitura DIRIGIDA pelas faixas das peças-chave.</passo>
      <passo>GRAVAR (Write) o relatório em $WORKSPACE/$NUMERO-relatorio.md. ATENÇÃO: este relatório
             INTEGRA o acórdão publicado — no corpo, nenhum [VERIFICAR]/[LACUNA] e nenhum markdown;
             dado ausente vira "Id. NÃO CONSTA"/"fls. NÃO CONSTA" e a dúvida vai na linha de status.</passo>
      <passo>Responder APENAS: "relatorio OK | $NUMERO-relatorio.md" (sufixo "| pendente: <assunto>"
             se houver dúvida) — NÃO imprimir o documento.</passo>
      <restricoes>Descritivo, sem análise; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      Sufixo na linha de status → contingência pendencia_de_redator (origem RELATÓRIO).
      Validar: `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapa relatorio` (âncoras +
      checagem de publicação; exit 1 → etapa_invalida).
    </acao_orquestrador>
    <transicao>Gate 0 → Etapa 3.</transicao>
  </etapa>

  <etapa numero="3" nome="Triagem recursal ($MODELO_RACIOCINIO) — SEMPRE obrigatória">
    <retomada>Se "triagem" NÃO está em PENDENTES → NÃO despachar a Task (passo 1). Os passos 2-5
    rodam SEMPRE (scripts baratos e idempotentes; é deles que sai a rota desta execução).</retomada>
    <acao_orquestrador>
      1. [SÓ se "triagem" em PENDENTES] Task — `subagent_type: general-purpose`, `model: $MODELO_RACIOCINIO`:
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DE TRIAGEM. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/segundo-grau/triador-recursal.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $PERFIL_PATH — MCP de jurisprudência do $TRIBUNAL, sintaxe e limites de cobertura.</passo>
      <passo>Carregar as ferramentas com ToolSearch ANTES de buscar: o BNP
             (select:mcp__bnp-api__buscar_precedentes) e o MCP que o perfil indica. MCP que não
             carregar → contingência se_mcp_indisponivel do seu prompt.</passo>
      <passo>Read: $WORKSPACE/$NUMERO-relatorio.md; opcional: $WORKSPACE/$NUMERO-linha-tempo.md.
             Órgão julgador: $TURMA.</passo>
      <passo>Conferir o OBJETO (passo 1.5 do seu método): embargos de declaração pendentes contra
             acórdão → desvio "embargos"; recurso que perdeu o objeto → desvio "prejudicado"; ambos
             SEM buscas. Senão, reconhecimento (máx 4 buscas) e classificação tese × prova.</passo>
      <passo>GRAVAR (Write) a triagem em $WORKSPACE/$NUMERO-triagem.md (exatamente UM bloco ```json)
             e $WORKSPACE/fontes-triagem.json (verbatim EXATO; nada encontrado → {"fontes": []}).</passo>
      <passo>Responder APENAS: "triagem OK | $NUMERO-triagem.md" — NÃO imprimir os documentos.</passo>
      <restricoes>Só rotear; rota [] exige justificativa_rotina afirmativa; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      Validar: `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapa triagem` (âncoras + contrato
      C2; exit 1 → etapa_invalida).
      2. Merge de fontes — SEMPRE: `Bash: python scripts/merge_fontes.py "$WORKSPACE" --id "$NUMERO"`
         (exit 1 = rejeitados NOMEADOS → contingência fontes_rejeitadas).
      3. Rota — SEMPRE: `Bash: python scripts/verificar_voto.py "$WORKSPACE" --rota`
         → "DESVIO: embargos" na 1ª linha → contingência desvio_embargos; ENCERRAR o tronco aqui.
         → "DESVIO: prejudicado" → contingência desvio_prejudicado (rota direta, sem trilhos).
         → "ROTA: ..." + linhas TEMA:/FATO: ($TEMAS/$FATOS) e, em rota direta, JUSTIFICATIVA:.
         (exit 1 → contingência rota_invalida.)
      4. TodoWrite DINÂMICO: {content: "Etapa 3.6 - Trilho de pesquisa"} se "pesquisa" na ROTA;
         {content: "Etapa 3.7 - Trilho probático"} se "probatica" — nascendo completed se
         `verificar_voto.py "$WORKSPACE" --etapas <etapas do trilho> --gate` já sair 0.
      5. Proveniência EARLY — SÓ se a ROTA não contiver "pesquisa" (senão, quem audita é a 3.6):
         `Bash: python scripts/verificar_proveniencia.py "$WORKSPACE"` (sem --exigir-citaveis; exit 2
         "fontes inexistente" → nenhum parcial, seguir; NAO_ENCONTRADA → contingência
         proveniencia_nao_confirmada; SEM_ADAPTADOR/BASE_INDISPONIVEL aqui é só registro no livro:
         `printf '%s\n' "PROVENIÊNCIA | <linha>" >> "$PENDENCIAS"`).
    </acao_orquestrador>
    <transicao>DESVIO embargos → bastão ao /pipeline-embargos (fim). "pesquisa" na ROTA → Etapa 3.6.
    Senão "probatica" → Etapa 3.7. Senão (rota direta ou prejudicado) → Etapa 4.</transicao>
  </etapa>

  <etapa numero="3.6" nome="Trilho de pesquisa (condicional) — SÓ SE 'pesquisa' na ROTA" modo="paralelo">
    <retomada>`Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapas pesquisa-tribunal,pesquisa-bnp`
    → a linha PENDENTES é o plano DO TRILHO (INDISPONIVEL registrada em disco não é cobrada). Nada
    pendente → pular ao passo 3.</retomada>
    <acao_orquestrador>
      1. As pesquisas pendentes em PARALELO (2 Tasks no MESMO turno), ambas `subagent_type:
         general-purpose`, `model: sonnet` (Extração). Pesquisa do tribunal:
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DE PESQUISA. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/pesquisa/pesquisador-jurisprudencia-trf.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $PERFIL_PATH — MCP do $TRIBUNAL, sintaxe, cobertura, frescor, adaptador de proveniência.</passo>
      <passo>Carregar com ToolSearch o MCP que o perfil indica ANTES de qualquer busca.</passo>
      <passo>TEMAS (da triagem): $TEMAS. Órgão julgador do recurso: $TURMA. Processo: $NUMERO.</passo>
      <passo>GRAVAR (Write) o relatório em $WORKSPACE/$NUMERO-pesquisa-tribunal.md e o parcial em
             $WORKSPACE/fontes-tribunal.json (Contrato C1; só os julgados destacados; verbatim literal).</passo>
      <passo>Responder APENAS: "pesquisa-tribunal OK | $NUMERO-pesquisa-tribunal.md" (com "| LACUNA:
             <motivo>" se houver) — NÃO imprimir o documento.</passo>
      <restricoes>NUNCA fixar MCP de memória; NUNCA tratar base defasada como vigente; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
         Pesquisa BNP (agente reusado):
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DE PESQUISA. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/pesquisa/pesquisador-bnp.md — sua capacidade; siga fielmente.</passo>
      <passo>Carregar com ToolSearch: select:mcp__bnp-api__buscar_precedentes,mcp__bnp-api__gerar_relatorio_precedentes.</passo>
      <passo>TEMAS (da triagem): $TEMAS. Prefixo $ID = $NUMERO. Sintaxe BNP: +termo -termo "frase".</passo>
      <passo>GRAVAR (Write) $WORKSPACE/$NUMERO-pesquisa-bnp.md e $WORKSPACE/selecao-bnp.json (NÃO
             gravar fontes-bnp.json — quem grava é o script de captura).</passo>
      <passo>Responder APENAS: "pesquisa-bnp OK | $NUMERO-pesquisa-bnp.md" — NÃO imprimir o documento.</passo>
      <restricoes>Teses EXATAS; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      2. Validar CADA uma: `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapa pesquisa-tribunal`
         (idem pesquisa-bnp). Exit 1 → redespachar SÓ a reprovada (máx 2); falha 2x ou MCP desconectado
         → contingência fonte_indisponivel. Linha de status com "| LACUNA:" → registrar no livro.
         Para a BNP validada: `Bash: python scripts/capturar_fontes.py "$WORKSPACE" --selecao selecao-bnp.json --id "$NUMERO"`
         (exit 1 = rejeições NOMEADAS, não-fatal → fontes_rejeitadas).
      3. Merge: `Bash: python scripts/merge_fontes.py "$WORKSPACE" --id "$NUMERO"` (contingência fontes_rejeitadas).
      4. Proveniência EARLY: `Bash: python scripts/verificar_proveniencia.py "$WORKSPACE"` (sem
         --exigir-citaveis). Toda linha SEM_ADAPTADOR/BASE_INDISPONIVEL → livro ("PROVENIÊNCIA | <linha>")
         — é a lista "Fontes para Conferência Humana" que vai à prancha. NAO_ENCONTRADA → contingência.
      5. Fechamento EXIT-CODED: `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapas pesquisa-tribunal,pesquisa-bnp --gate`
         (exit 1 → PARAR e reportar).
    </acao_orquestrador>
    <transicao>"probatica" na ROTA → Etapa 3.7. Senão → Etapa 4.</transicao>
  </etapa>

  <etapa numero="3.7" nome="Trilho probático ADVERSARIAL (condicional) — SÓ SE 'probatica' na ROTA" modo="paralelo">
    <retomada>`Bash: python scripts/verificar_probatica.py "$WORKSPACE" --etapas inventario,tese-pro-autor,tese-pro-reu,replica-pro-autor,replica-pro-reu,consolidado-adversarial`
    → PENDENTES é o plano DO TRILHO. Nada pendente → pular ao passo 5.</retomada>
    <acao_orquestrador>
      ESCOPO DEVOLVIDO (vale para TODOS os invólucros do trilho): no 2º grau o tribunal só julga o
      que foi devolvido. Cada subagente lê, além das suas entradas, a seção "## ADMISSIBILIDADE
      APARENTE E MATÉRIA DEVOLVIDA" de $WORKSPACE/$NUMERO-triagem.md e LIMITA as probandas aos
      capítulos devolvidos; prova que só interessa a capítulo não impugnado fica fora. Focos: $FATOS.
      CASCATA: tese regenerada agora → AMBAS as réplicas re-rodam; tese ou réplica regenerada agora →
      a síntese re-roda.
      1. Inventário [se pendente] — Task `general-purpose`, `model: sonnet`:
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE INVENTARIADOR. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/analise/inventariador-probatica.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $WORKSPACE/$NUMERO-triagem.md — SÓ a seção da matéria devolvida (ESCOPO).</passo>
      <passo>Read: $AUTOS (multi-pass do seu prompt). Catalogar com ZERO valoração, com atenção aos
             FOCOS: $FATOS, dentro do ESCOPO devolvido.</passo>
      <passo>GRAVAR (Write) $WORKSPACE/$NUMERO-inventario.md — abre "# INVENTÁRIO PROBATÓRIO", fecha
             "É o que satisfaz inventariar do acervo probatório.", com acentos.</passo>
      <passo>Responder APENAS: "inventario OK | $NUMERO-inventario.md".</passo>
      <restricoes>Só catalogação; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      Validar: `Bash: python scripts/verificar_probatica.py "$WORKSPACE" --etapa inventario`.
      2. TESES em PARALELO (pendentes; 2 Tasks no mesmo turno, `general-purpose`, `model: $MODELO_RACIOCINIO`) — pró-autor:
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DO TRIBUNAL PROBATÓRIO — ADVOGADO DA PRETENSÃO. EXECUTE DIRETAMENTE,
      SEM PREÂMBULO. MODO ARQUIVO, RODADA 1 (TESE).
      <passo>Read: .claude/agents/tribunal/acusador-probatico.md — siga o MODO ARQUIVO (RODADA 1 — TESE).</passo>
      <passo>Read: $WORKSPACE/$NUMERO-triagem.md (seção da matéria devolvida = ESCOPO),
             $WORKSPACE/$NUMERO-linha-tempo.md, $WORKSPACE/$NUMERO-relatorio.md, $WORKSPACE/$NUMERO-inventario.md
             e $AUTOS (dirigido).</passo>
      <passo>Construir a tese da pretensão SÓ sobre as probandas dos capítulos devolvidos, com foco em
             $FATOS, e GRAVAR (Write) $WORKSPACE/$NUMERO-tese-pro-autor.md — PRIMEIRA linha
             "# Tese Pró-Autor", ÚLTIMA linha "Tese pró-autor concluída.", com acentos.</passo>
      <passo>Responder APENAS: "tese-pro-autor OK | $NUMERO-tese-pro-autor.md".</passo>
      <restricoes>MODO ARQUIVO (NUNCA SendMessage, TaskUpdate ou TodoWrite); NUNCA inventar prova;
      escala ordinal, sem probabilidades numéricas.</restricoes>
      ═══════════════════════════════════════════════════════════════════
         REGRA DOS DESPACHOS DERIVADOS (pró-réu, réplicas, mediador): cada um é uma Task própria com o
         MESMO invólucro do pró-autor acima — subagent_type: general-purpose, model: $MODELO_RACIOCINIO,
         Passo 1 = Read do agente indicado, GRAVAR no arquivo indicado, responder 1 linha, MODO ARQUIVO —
         trocando só os valores listados a seguir.
         Pró-réu (espelho): .claude/agents/tribunal/defensor-probatico.md (ADVOGADO DA RESISTÊNCIA);
         grava $WORKSPACE/$NUMERO-tese-pro-reu.md, "# Tese Pró-Réu" / "Tese pró-réu concluída.";
         responde "tese-pro-reu OK | $NUMERO-tese-pro-reu.md". Mesmo ESCOPO e mesmos FOCOS.
         Validar cada uma: `verificar_probatica.py "$WORKSPACE" --etapa tese-pro-autor` (idem tese-pro-reu);
         2ª falha → PARAR (o mediador exige as duas).
      3. RÉPLICAS CRUZADAS em PARALELO [pendentes OU qualquer tese regenerada agora] — `model: $MODELO_RACIOCINIO`.
         Réplica pró-autor: Read acusador-probatico.md (MODO ARQUIVO, RODADA 2 — RÉPLICA); Read PRIMEIRO
         a PRÓPRIA tese ($NUMERO-tese-pro-autor.md), DEPOIS a adversária ($NUMERO-tese-pro-reu.md);
         grava réplica CURTA (≤ 1/2 da tese adversária) em $WORKSPACE/$NUMERO-replica-pro-autor.md com a
         seção OBRIGATÓRIA "## Fidelidade à Tese" (probanda × MANTIDA/REFORÇADA/ABANDONADA × razão;
         ABANDONADA exige prova nova adversária nomeada), "# Réplica Pró-Autor" / "Réplica pró-autor
         concluída."; responde "replica-pro-autor OK | ...". Réplica pró-réu: espelho com
         defensor-probatico.md, própria tese $NUMERO-tese-pro-reu.md primeiro, arquivo
         $NUMERO-replica-pro-reu.md, "# Réplica Pró-Réu" / "Réplica pró-réu concluída.". Ambas no ESCOPO
         devolvido; MODO ARQUIVO; PROIBIDO abandonar probanda sem prova nova adversária nomeada.
         Validar: `verificar_probatica.py "$WORKSPACE" --etapa replica-pro-autor` (idem pro-reu).
      4. SÍNTESE [consolidado pendente OU tese/réplica regenerada agora] — `general-purpose`, `model: $MODELO_RACIOCINIO`:
         Read .claude/agents/tribunal/juiz-mediador.md (MODO ARQUIVO); Read inventário, as 2 teses, as
         2 réplicas, o relatório e a seção da matéria devolvida da triagem; síntese POR PROBANDA dos
         capítulos devolvidos, com coluna Contraprova, "Consistência Tese-Réplica" e "Pontos de
         Convergência" abrindo por "Convergências genuínas entre as partes:"; GRAVAR
         $WORKSPACE/$NUMERO-probatica-consolidado.md ("# SÍNTESE PROBATÓRIA CONSOLIDADA" / "Síntese
         probatória consolidada concluída."); responder "consolidado OK | $NUMERO-probatica-consolidado.md".
         NUNCA decidir o mérito; capitulação de réplica não é convergência.
         Validar: `Bash: python scripts/verificar_probatica.py "$WORKSPACE" --etapa consolidado-adversarial`.
      5. Fechamento EXIT-CODED:
         `Bash: python scripts/verificar_probatica.py "$WORKSPACE" --etapas inventario,tese-pro-autor,tese-pro-reu,replica-pro-autor,replica-pro-reu,consolidado-adversarial --gate`
         E `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapas probatica --gate` (exit 1 → PARAR).
    </acao_orquestrador>
    <transicao>Gates 0 → Etapa 4.</transicao>
  </etapa>

  <etapa numero="4" nome="Análise recursal ($MODELO_RACIOCINIO) — válvula ESCALAR">
    <retomada>Se "analise" NÃO está em PENDENTES → pular. ("[ESCALAR] analise" na varredura conta
    como pendente — tratar pelo passo 3, nunca por redespacho cego.)</retomada>
    <acao_orquestrador>
      1. Task — `subagent_type: general-purpose`, `model: $MODELO_RACIOCINIO`; passos condicionais só se
         o artefato existir (`Bash: test -f`):
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DE ANÁLISE RECURSAL. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/segundo-grau/analisador-recursal.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $DISCIPLINA_PATH — a disciplina de devolutividade (prevalece sobre o resumo do seu prompt).</passo>
      <passo>Read: $PERFIL_PATH (regimento, sessão, art. 942: o que não estiver documentado é [VERIFICAR: regimento]).</passo>
      <passo>Read: $WORKSPACE/$NUMERO-relatorio.md, $WORKSPACE/$NUMERO-triagem.md e $WORKSPACE/$NUMERO-linha-tempo.md.</passo>
      <passo>[SE existir] Read: $WORKSPACE/$NUMERO-fontes.json (verbatim da custódia).</passo>
      <passo>[SE o trilho 3.6 rodou] Read: $WORKSPACE/$NUMERO-pesquisa-tribunal.md e/ou
             $WORKSPACE/$NUMERO-pesquisa-bnp.md — dialogue com a pesquisa, não a repita.</passo>
      <passo>[SE o trilho 3.7 rodou] Read: $WORKSPACE/$NUMERO-probatica-consolidado.md — use a síntese.</passo>
      <passo>[SE a rota impressa trouxe "DESVIO: prejudicado"] A triagem apontou prejudicialidade
             (JUSTIFICATIVA: <linha do --rota>): examine-a PRIMEIRO à luz dos autos (contingência
             se_recurso_prejudicado); confirmada, o resultado é não conhecimento/prejudicado, sem mérito.</passo>
      <passo>Autos para leitura DIRIGIDA pelas faixas de página: $AUTOS.</passo>
      <passo>GRAVAR (Write) a análise em $WORKSPACE/$NUMERO-analise.md e os citáveis em
             $WORKSPACE/$NUMERO-citaveis.json (JSON puro; praxe = lista de strings; referência copiada
             EXATAMENTE como aparece nas pesquisas/fontes.json).</passo>
      <passo>Responder APENAS: "analise OK | $NUMERO-analise.md" — NÃO imprimir o documento.</passo>
      <restricoes>Nada além do devolvido; aspas só com lastro verbatim; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      2. Validar:
         a) `Bash: test -f "$WORKSPACE/$NUMERO-citaveis.json"` — ausente → redespachar com o motivo
            "citaveis.json não foi gravado — grave-o conforme <marcacao_citaveis>" (máx 2; persistindo, PARAR).
         b) `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapa analise`
            → 0: seguir ao c). 1: etapa_invalida. 3: "[ESCALAR] analise: <trilhos> — <motivo>" → passo 3.
         c) Gate verbatim da análise (documento interno):
            `Bash: python scripts/verificar_citacoes.py "$WORKSPACE" --doc=-analise.md`
            (forma "--doc=" obrigatória). Exit 1 → redespachar a análise com o sufixo_citacoes (conta nas
            2 tentativas da etapa).
      3. ESCALAR (MÁXIMO 1 ciclo por processo; detecção PERSISTENTE em disco):
         (i) Trilhos pedidos na linha [ESCALAR] (motivo vem normalizado; usar como está).
         (ii) Para cada trilho pedido, o trilho JÁ passa no gate?
              pesquisa:  `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapas pesquisa-tribunal,pesquisa-bnp --gate`
              probatica: `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapas probatica --gate`
              Todos já passam → redespachar a análise (mesmo invólucro) com a marca anexada:
              "[ESCALADA JÁ UTILIZADA] — conclua com os insumos disponíveis, registrando a limitação."
         (iii) Senão: rodar o(s) trilho(s) faltante(s) com a mecânica da Etapa 3.6/3.7 (TEMAS/FATOS da
              triagem, complementados pelo motivo do [ESCALAR]; na pesquisa, merge_fontes.py e
              proveniência early) e redespachar a análise com o insumo novo E a mesma marca.
         (iv) `--etapa analise` de novo: 0 → seguir ao 2c; 3 DE NOVO → contingência escalar_segunda_vez.
    </acao_orquestrador>
    <transicao>Gates 0 → Etapa 5.</transicao>
  </etapa>

  <etapa numero="5" nome="Voto ($MODELO_RACIOCINIO) — minuta limpa">
    <retomada>Se "voto" NÃO está em PENDENTES → não despachar; o gate da minuta limpa (passo 3b) roda
    mesmo assim e, reprovando, o voto é regenerado com o sufixo_minuta.</retomada>
    <acao_orquestrador>
      1. Task — `subagent_type: general-purpose`, `model: $MODELO_RACIOCINIO`:
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DE REDAÇÃO. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/redacao/redator-voto.md — sua capacidade; siga fielmente (<regime_minuta_limpa>).</passo>
      <passo>Read: $WORKSPACE/$NUMERO-analise.md (matriz capítulo × resultado: o resultado é LEI).</passo>
      <passo>Read: $WORKSPACE/$NUMERO-citaveis.json — a ÚNICA lista de referências permitidas.</passo>
      <passo>Read: $WORKSPACE/$NUMERO-relatorio.md e $PERFIL_PATH (forma do fecho, se documentada).</passo>
      <passo>NÃO escreva números CNJ no voto, salvo os que constem dos citáveis (nem o do próprio
             recurso, nem o da sentença, nem o de conexo): o gate da minuta limpa lê todo número CNJ
             como referência jurisprudencial.</passo>
      <passo>GRAVAR (Write) o voto em $WORKSPACE/$NUMERO-voto.md (linha VOTO ... linha "É como voto.").</passo>
      <passo>Responder APENAS: "redator-voto OK | $NUMERO-voto.md" (com o sufixo de pendência do seu
             prompt, se houver) — NÃO imprimir o voto.</passo>
      <restricoes>Zero aspas de fonte; zero markdown; nada além do devolvido; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      2. Linha de status: "PENDENTE" → contingência redator_bloqueado (origem: análise → PARAR).
         Sufixo "| precisa de citável: <tema>" ou outra pendência → contingência pendencia_de_redator (VOTO).
      3. Validação DUPLA:
         a) `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapa voto` (exit 1 → etapa_invalida).
         b) `Bash: python scripts/verificar_minuta_limpa.py "$WORKSPACE" --doc=-voto.md --a-partir-de VOTO`
            (sem --exigir-vereditos; exit 1 → regenerar com o sufixo_minuta, máx 2; numa regeneração da
            Etapa 8, a linha "paráfrase(s) refutada(s)" vem do veredito ANTIGO e não conta aqui).
    </acao_orquestrador>
    <transicao>Gates a) e b) em 0 → Etapa 6.</transicao>
  </etapa>

  <etapa numero="6" nome="Ementa (sonnet) — deriva do voto">
    <retomada>Se "ementa" NÃO está em PENDENTES E o voto não foi (re)gerado nesta execução → pular
    (o gate da minuta limpa do passo 3b roda mesmo assim). Voto novo → a ementa SEMPRE é refeita.</retomada>
    <acao_orquestrador>
      1. Task — `subagent_type: general-purpose`, `model: sonnet` (Extração: espelha, não decide):
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE DE REDAÇÃO DE EMENTA. EXECUTE DIRETAMENTE, SEM PREÂMBULO.
      <passo>Read: .claude/agents/redacao/redator-ementa.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $PERFIL_PATH (campo formato_ementa) e $FORMATO_EMENTA_PATH (seções e verbetação).</passo>
      <passo>Read: $WORKSPACE/$NUMERO-voto.md — a ementa espelha o voto, sem acrescentar nada.</passo>
      <passo>Read: $WORKSPACE/$NUMERO-citaveis.json — referência jurisprudencial e número CNJ só entram se constarem dos citáveis.</passo>
      <passo>GRAVAR (Write) a ementa em $WORKSPACE/$NUMERO-ementa.md (abre EMENTA, fecha [FIM_EMENTA];
             no corpo, nenhum colchete de pendência e nenhum número CNJ ou referência que o voto não cite).</passo>
      <passo>Responder APENAS: "redator-ementa OK | $NUMERO-ementa.md" (com "| pendente: <assunto>" se
             houver) — NÃO imprimir o documento.</passo>
      <restricoes>Sem markdown; sem aspas de fonte; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      2. Linha de status: "BLOQUEADO" → contingência redator_bloqueado (origem: voto → PARAR).
         "| pendente: <assunto>" → contingência pendencia_de_redator (EMENTA).
      3. Validação DUPLA:
         a) `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapa ementa` (exit 1 → etapa_invalida).
         b) `Bash: python scripts/verificar_minuta_limpa.py "$WORKSPACE" --doc=-ementa.md --a-partir-de EMENTA`
            (exit 1 → regenerar com o sufixo_minuta, máx 2; mesma ressalva do veredito antigo).
    </acao_orquestrador>
    <transicao>Gates a) e b) em 0 → Etapa 7.</transicao>
  </etapa>

  <etapa numero="7" nome="Montagem do acórdão (script, sem LLM)">
    <retomada>Se "acordao" NÃO está em PENDENTES E relatório/voto/ementa não foram regenerados nesta
    execução → pular. (O gate acusa o acórdão como desatualizado quando uma entrada fica mais nova.)</retomada>
    <acao_orquestrador>
      `Bash: python scripts/merge_voto.py "$WORKSPACE"`
      → "[OK] acordao -> ..." (exit 0). "[ERRO] entrada <etapa> ..." → o defeito é da etapa apontada:
      voltar a ela (Etapa 2, 5 ou 6), nunca ao merge.
    </acao_orquestrador>
    <transicao>Exit 0 → Etapa 8.</transicao>
  </etapa>

  <etapa numero="8" nome="Auditoria de paráfrase e de coerência (paralelo) — regeneração dirigida">
    <retomada>Juiz-paráfrase: pular se
    `Bash: test "$WORKSPACE/$NUMERO-vereditos-parafrase.md" -nt "$WORKSPACE/$NUMERO-acordao.md"` sair 0
    (vereditos mais novos que o acórdão). Coerência: pular se "coerencia" NÃO está em PENDENTES; se o
    `--etapa coerencia` de um acórdão atual já sai 4 (DIVERGENTE gravado numa execução anterior), ir
    direto ao passo 3 sem redespachar o verificador.</retomada>
    <acao_orquestrador>
      1. Despachar NO MESMO TURNO (só os necessários), ambos `subagent_type: general-purpose`,
         `model: $MODELO_RACIOCINIO`. Juiz-paráfrase (reusado):
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE JUIZ DE PARÁFRASE. EXECUTE DIRETAMENTE, SEM PREÂMBULO. MODO ARQUIVO.
      <passo>Read: .claude/agents/revisao/juiz-parafrase.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $WORKSPACE/$NUMERO-citaveis.json e $WORKSPACE/$NUMERO-fontes.json (âncoras).</passo>
      <passo>Read: $WORKSPACE/$NUMERO-acordao.md — NESTE pipeline a minuta é o acórdão: examine a
             EMENTA (do início até a linha RELATÓRIO) e o VOTO (da linha VOTO ao fim); o RELATÓRIO fica
             fora (relato de parte é livre). Onde o seu prompt diz sentença/FUNDAMENTAÇÃO, leia acórdão/VOTO.</passo>
      <passo>GRAVAR (Write) $WORKSPACE/$NUMERO-vereditos-parafrase.md no formato do seu prompt
             (linha "REFUTADAS: N" no topo; um veredito por citável).</passo>
      <passo>Responder APENAS: "Vereditos gravados: N citáveis, M refutadas."</passo>
      <restricoes>MODO ARQUIVO; NUNCA julgar sem âncora; NUNCA editar a minuta; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
         Verificador de coerência:
      ═══════════════════════════════════════════════════════════════════
      VOCÊ É UM SUBAGENTE CONFERENTE DE COERÊNCIA. EXECUTE DIRETAMENTE, SEM PREÂMBULO. MODO ARQUIVO.
      <passo>Read: .claude/agents/revisao/verificador-coerencia-acordao.md — sua capacidade; siga fielmente.</passo>
      <passo>Read: $WORKSPACE/$NUMERO-acordao.md e $WORKSPACE/$NUMERO-analise.md (matriz aprovada).</passo>
      <passo>Opcional: Read: $DISCIPLINA_PATH (verificação (e)) e $WORKSPACE/$NUMERO-citaveis.json.</passo>
      <passo>GRAVAR (Write) $WORKSPACE/$NUMERO-coerencia.md — abre "# Conferência de Coerência do
             Acórdão"; cada divergência em bloco "DIVERGENCIA k" com "RESPONSAVEL: VOTO|EMENTA"; ÚLTIMA
             linha "VEREDITO: COERENTE" ou "VEREDITO: DIVERGENTE — <n> itens" (n = nº de blocos).</passo>
      <passo>Responder APENAS: "verificador-coerencia-acordao OK | $NUMERO-coerencia.md".</passo>
      <restricoes>Julga, não reescreve; NUNCA usar TodoWrite.</restricoes>
      ═══════════════════════════════════════════════════════════════════
      2. Ler os vereditos POR SCRIPT (nunca o documento):
         a) `Bash: python scripts/verificar_voto.py "$WORKSPACE" --etapa coerencia`
            → 0 COERENTE; 4 DIVERGENTE (linhas "RESPONSAVEL: <VOTO|EMENTA> (item k)"); 1 → etapa_invalida
            (redespachar o verificador com o sufixo_gate).
         b) `Bash: grep -m1 '^REFUTADAS:' "$WORKSPACE/$NUMERO-vereditos-parafrase.md"` → N
            (arquivo ausente ou sem a linha → redespachar o juiz-paráfrase, máx 2).
      3. REGENERAÇÃO DIRIGIDA (se exit 4 OU REFUTADAS > 0; máx 2 ciclos — depois contingência
         divergencia_persistente):
         - RESPONSÁVEIS = {RESPONSAVEL das linhas do gate} ∪ {VOTO, se REFUTADAS > 0}.
         - VOTO ∈ RESPONSÁVEIS → redespachar a Etapa 5 (mesmo invólucro + sufixo_coerencia com
           <VOTO>) e seus gates; em CASCATA, a Etapa 6 (a ementa deriva do voto).
         - Só EMENTA → redespachar a Etapa 6 com o sufixo_coerencia (<EMENTA>) e seus gates.
         - Remontar (Etapa 7) e repetir esta Etapa 8 inteira (as duas auditorias: o acórdão mudou).
    </acao_orquestrador>
    <transicao>Coerência exit 0 E REFUTADAS: 0 → Etapa 9.</transicao>
  </etapa>

  <etapa numero="9" nome="Gates finais, proveniência, prancha e resumo">
    <acao_orquestrador>
      1. Gate global: `Bash: python scripts/verificar_voto.py "$WORKSPACE" --gate` (exit 1 → algo
         regrediu; reportar o output e PARAR).
      2. Minuta limpa no ACÓRDÃO (documento de publicação inteiro; referências a partir do VOTO):
         `Bash: python scripts/verificar_minuta_limpa.py "$WORKSPACE" --doc=-acordao.md --a-partir-de VOTO --exigir-vereditos`
         Exit 1 → contingência minuta_impura (voltar à Etapa 8; máx 1 volta).
      3. Proveniência FINAL (pré-assinatura), com a saída guardada em disco para a prancha:
         `Bash: mkdir -p "$WORKSPACE/custodia" && python scripts/verificar_proveniencia.py "$WORKSPACE" --exigir-citaveis > "$WORKSPACE/custodia/proveniencia-final.txt"; echo "exit=$?"`
         `Bash: grep -E 'NAO_ENCONTRADA|SEM_ADAPTADOR|BASE_INDISPONIVEL|sem fonte CONFIRMADA|citaveis.json ausente|\[FIM\]' "$WORKSPACE/custodia/proveniencia-final.txt"`
         → NAO_ENCONTRADA → contingência proveniencia_nao_confirmada (re-merge e nova rodada; máx 2).
         → SEM_ADAPTADOR/BASE_INDISPONIVEL/"citável sem fonte CONFIRMADA" → registrar cada linha no
           livro ("PROVENIÊNCIA | <linha>") e marcar o status final como BLOQUEADO PARA ASSINATURA
           AUTOMÁTICA. Fonte de TRF sem adaptador NUNCA conta como confirmada.
      4. Prancha: `Bash: python scripts/gerar_prancha.py "$WORKSPACE"` → $NUMERO-conferencia-fontes.md.
         Anexar em seguida (a prancha é regenerada a cada rodada; o anexo vem logo depois), com
         $TRIBUNAL e $PERFIL_PATH já substituídos:
         `Bash: { printf '\n## Pendências e ressalvas do pipeline-voto\n\n'; test -f "$PENDENCIAS" && awk '!v[$0]++ {print "- " $0}' "$PENDENCIAS"; printf '\n### Ressalvas do perfil (%s)\n\n' "$TRIBUNAL"; grep 'A CONFERIR' "$PERFIL_PATH" | sed 's/^/- /'; } >> "$WORKSPACE/$NUMERO-conferencia-fontes.md"`
         A prancha integra a entrega ao relator e roda TAMBÉM quando a proveniência bloqueia (ela é o
         insumo da decisão humana).
      5. Rota para o resumo (sem ler a triagem): `Bash: python scripts/verificar_voto.py "$WORKSPACE" --rota`.
         Pendências: `Bash: test -f "$PENDENCIAS" && awk '!v[$0]++' "$PENDENCIAS"`.
      6. Resumo ao usuário, no formato mínimo:
         ```
         [INICIO] pipeline-voto $NUMERO -> $WORKSPACE
         [OK] tribunal: $TRIBUNAL (conferido pelo CNJ) — perfil $PERFIL_PATH
         [OK] autos: $AUTOS (extraídos em <data>)
         [OK] regime de modelos: raciocínio=$MODELO_RACIOCINIO; extração=sonnet
         [OK] rota: <ROTA: ...> (+ JUSTIFICATIVA/DESVIO quando houver); trilhos rodados; escalada: sim|não
         [OK] acórdão: $WORKSPACE/$NUMERO-acordao.md (ciclos de regeneração dirigida: k)
         [OK] coerência: COERENTE | paráfrase: REFUTADAS: 0
         [OK|ERRO] proveniência: <linha [FIM] do gate final>; itens à conferência humana: n
         [OK] prancha: $WORKSPACE/$NUMERO-conferencia-fontes.md
         [ERRO] pendência: <uma linha por pendência do livro>   (ou "[OK] pendências: nenhuma")
         [OK] artefatos: REAPROVEITADOS <lista> × GERADOS AGORA <lista>
         [FIM] status: PRONTO PARA CONFERÊNCIA DO RELATOR | BLOQUEADO PARA ASSINATURA AUTOMÁTICA (<motivo>)
         ```
    </acao_orquestrador>
  </etapa>

</fases_pipeline>

<resumo_arquitetura>
PIPELINE VOTO v1.0 — acórdão de 2º grau multi-TRF, triagem + trilhos condicionais + dois tempos
│   [$MOD] = $MODELO_RACIOCINIO (sonnet; opus com --opus). [sonnet] fixo = Extração.
│   Toda Task: subagent_type general-purpose + model explícito (MCP por ToolSearch).
├── 0   Preparação: $NUMERO → $TRIBUNAL=TRF2 (conferido no CNJ) → $PERFIL_PATH; $WORKSPACE=data/voto/$NUMERO;
│       autos: TXT (cp -p) | PDF (converter-pdf --strict-ocr) | download (só perfil com download_automatico: sim) | PARAR;
│       frescor do TXT; verificar_voto.py → PENDENTES (o plano)
├── 1   Linha do tempo recursal [sonnet] → $NUMERO-linha-tempo.md
├── 2   Relatório               [sonnet] → $NUMERO-relatorio.md (integra o acórdão: gate de publicação)
├── 3   Triagem (SEMPRE)        [$MOD, MCP] → $NUMERO-triagem.md + fontes-triagem.json
│       --etapa triagem (C2) → merge_fontes.py → --rota: DESVIO embargos → /pipeline-embargos (fim)
│       | DESVIO prejudicado → Etapa 4 sem trilhos | ROTA/TEMA/FATO; proveniência early se sem pesquisa
├── 3.6 [SE pesquisa] pesquisador-jurisprudencia-trf ∥ pesquisador-bnp [sonnet, MCP]
│       → capturar_fontes (bnp) → merge_fontes → proveniência early (SEM_ADAPTADOR → livro/prancha)
├── 3.7 [SE probatica] inventário [sonnet] → teses ∥ [$MOD] → réplicas ∥ [$MOD] → mediador [$MOD]
│       escopo = matéria devolvida da triagem; gate verificar_probatica + verificar_voto --etapas probatica
├── 4   Análise recursal        [$MOD] → $NUMERO-analise.md + $NUMERO-citaveis.json
│       (disciplina + perfil injetados); --etapa analise (3 = ESCALAR, 1 ciclo, persistido em disco);
│       verificar_citacoes.py --doc=-analise.md
├── 5   Voto                    [$MOD] → $NUMERO-voto.md (minuta limpa; sem CNJ fora dos citáveis)
│       pendências da linha de status → livro; PENDENTE → PARAR
├── 6   Ementa                  [sonnet] → $NUMERO-ementa.md (espelho do voto; BLOQUEADO → PARAR)
├── 7   merge_voto.py           [SCRIPT] → $NUMERO-acordao.md = EMENTA + RELATÓRIO + VOTO
├── 8   juiz-parafrase ∥ verificador-coerencia-acordao [$MOD]
│       DIVERGENTE (exit 4) / REFUTADAS > 0 → regenerar o RESPONSAVEL (VOTO → voto + ementa; EMENTA → ementa)
│       → remontar → reauditar (máx 2 ciclos)
└── 9   --gate → minuta limpa no acórdão (--a-partir-de VOTO --exigir-vereditos) → proveniência final
        (SEM_ADAPTADOR = conferência humana) → gerar_prancha.py + anexo de pendências/ressalvas → resumo
</resumo_arquitetura>

<checklist_orquestrador>
- [ ] $NUMERO extraído, $TRIBUNAL detectado (ou forçado) e $PERFIL_PATH existente?
- [ ] Autos em $AUTOS (cp -p / OCR estrito / download só com download_automatico: sim) e frescor reportado?
- [ ] Varredura da Etapa 0 rodou e as etapas válidas foram puladas?
- [ ] Toda Task com `subagent_type: general-purpose` e `model` explícito conforme a faixa?
- [ ] Triagem validada (âncoras + C2) e rota lida só por --rota? merge_fontes.py rodou após a triagem?
- [ ] ROTA respeitada; DESVIO embargos passou o bastão; DESVIO prejudicado seguiu sem trilhos?
- [ ] Trilhos fechados exit-coded (--etapas ... --gate); indisponibilidade registrada em disco?
- [ ] Trilho 3.7 limitado à matéria devolvida; réplicas leram a PRÓPRIA tese primeiro?
- [ ] Análise com disciplina + perfil injetados, citáveis gravados e verificar_citacoes.py verde?
- [ ] Escalada única, com detecção persistente em disco?
- [ ] Voto e ementa aprovados no gate de etapa E na minuta limpa? Pendências no livro?
- [ ] Acórdão montado por merge_voto.py (re-rodado após qualquer regeneração)?
- [ ] Coerência COERENTE e REFUTADAS: 0, lidos por script?
- [ ] Gate final, minuta limpa do acórdão, proveniência final e prancha (com anexo) antes do resumo?
- [ ] Fonte SEM_ADAPTADOR listada na prancha e nunca tratada como confirmada?
- [ ] Nenhum documento lido pelo orquestrador; subagentes responderam só a linha de status?
</checklist_orquestrador>
