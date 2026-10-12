# Perfil TRF2

> Campos no formato `chave: valor`, uma por linha, para leitura por orquestrador e agentes.
> Fonte: radar dos TRFs (`.claude/mcp-servers/README-radar-trfs.md`) e CLAUDE.md do projeto.
> Dado não documentado no repositório está marcado "A CONFERIR".

codigo_cnj: J=4, TR=02 (formato NNNNNNN-DD.AAAA.4.02.OOOO)
tribunal: Tribunal Regional Federal da 2ª Região
sede_estados: Rio de Janeiro (sede, A CONFERIR); RJ e ES
sistema_processual: eProc (A CONFERIR: o radar dos TRFs documenta o eProc do portal de JURISPRUDÊNCIA, não o sistema dos autos; confirmar nos autos recebidos). Se os autos forem eProc, as peças se identificam por evento, e a linha do tempo recursal deve citar o evento em vez do id de documento do PJe.
download_automatico: não. Nenhuma skill de download cobre o eProc do TRF2 (o pje-download atende hoje apenas o TRF5). Exigir PDF/TXT fornecido; converter com converter-pdf em modo OCR estrito.

## mcp_jurisprudencia
- servidor: trf2-eproc (eProc direto, página pública, sem login nem captcha)
- tool_busca: buscar_trf2
- tool_texto_integral: não há tool dedicada; o campo `<fonte>` de cada item é o link do PDF oficial do inteiro teor (padrão-ouro quando a ementa não basta)
- outras_tools: gerar_relatorio_trf2, listar_filtros_trf2
- sintaxe: eProc, case-insensitive, acentos ignorados. AND por espaço ou `e`; OR `ou`; NOT `nao`/`não`; frase entre aspas; proximidade `prox`; curinga `*` (prefixo, sufixo ou ambos). Filtros: campo (E/I/C), tipo_documento, origem, datas, processo, classe_processual, orgao_julgador e relator (string exata), precedente_relevante, agrupar_resultados.
- dialeto_eproc_trf2: origem 1 a 3 (sem Varas Federais); tipo de documento 1, 2, 3=Súmula, 4; precedente relevante por `chkPrecedenteRelevante`. Súmulas com base esparsa ou vazia.
- cobertura: viva (2026), medida em 14/07/2026. Cada item traz citação padronizada verbatim (`data-citacao`) e o link do inteiro teor.
- limites: só a página 1 por chamada (aumentar `max_resultados`); máximo de 100 por página; cuidar do payload (começar em `conciso`).
- formato: começar em `conciso`; `completo` só para casos já selecionados.
- fallback: o cjf-jurisprudencia genérico cobre o TRF2 só até ~2023 (base congelada); usar apenas para histórico e descartar resultado de base congelada para tema recente. BNP para vinculantes.

## proveniencia_adaptador
SEM_ADAPTADOR para trf2-eproc. Citações do TRF2 não são reauditadas na base oficial pelo gate: listar na prancha de conferência humana, nunca tratar como CONFIRMADA. A citação `data-citacao` e o PDF oficial facilitam a conferência humana.

## formato_ementa
cnj-estruturada (default). Ver `references/formato-ementa.md`. Modelo próprio do tribunal: A CONFERIR NO REGIMENTO.

## regimento
- composição e competência das Turmas e Seções: A CONFERIR NO REGIMENTO
- forma de convocação do colegiado ampliado (art. 942 CPC): A CONFERIR NO REGIMENTO
- regras de julgamento em sessão virtual (prazos, destaque, sustentação oral): A CONFERIR NO REGIMENTO
- dispositivo regimental sobre ementa e publicação do acórdão: A CONFERIR NO REGIMENTO

## regras_nacionais_cpc (valem para todos os TRFs; descritas sem transcrição)
- art. 942: se o julgamento de apelação não for unânime e o resultado for reforma da sentença de mérito, o julgamento prossegue com colegiado ampliado, com a possibilidade de os votos já proferidos serem revistos; incide também em outras hipóteses legais (ação rescisória com rescisão da decisão, agravo de instrumento que reforma decisão de mérito). O pipeline alerta o risco na análise; a convocação é ato do órgão julgador.
- art. 1.013: o efeito devolutivo da apelação limita o julgamento às questões e capítulos impugnados, com devolução em profundidade das questões já suscitadas; as exceções (ordem pública, causa madura, §3º) seguem a disciplina da skill disciplina-devolutividade-recursal.
- art. 85, §11: o tribunal, ao julgar o recurso, majora os honorários fixados anteriormente, observados os limites legais; não há majoração quando o recurso é provido, nem em remessa necessária sem recurso (alcance exato: A CONFERIR no texto da lei).
- art. 496: remessa necessária nas sentenças contra a Fazenda Pública e nas hipóteses legais, com exceções por valor da condenação e por conformidade com precedentes obrigatórios; conferir os limites de valor no texto da lei.
