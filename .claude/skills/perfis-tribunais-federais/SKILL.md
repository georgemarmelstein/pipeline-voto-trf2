---
name: perfis-tribunais-federais
description: Use when o pipeline de voto precisa do perfil do TRF2 — MCP de jurisprudência (trf2-eproc) e sua sintaxe, sistema processual (eProc), formato de ementa e particularidades regimentais e de sessão — a partir do número CNJ. Distribuição restrita ao TRF2. Keywords: perfil de tribunal, TRF2, número CNJ, eProc, ementa estruturada, regimento interno, art. 942, julgamento virtual.
---

<identidade>
  <papel>Referência do tribunal para o pipeline de voto, nesta distribuição restrita ao TRF2 (Rio de
  Janeiro e Espírito Santo).</papel>
  <dominio>Justiça Federal de 2º grau no TRF2: fonte de jurisprudência, sistema processual, formato de
  ementa e regimento.</dominio>
</identidade>

<quando_usar>
  - Etapa 0 do /pipeline-voto: conferir o tribunal pelo CNJ e carregar o perfil.
  - Triagem e pesquisa: saber qual MCP chamar (trf2-eproc) e com que sintaxe.
  - Redação da ementa: formato estruturado do CNJ (references/formato-ementa.md).
  - NÃO usar para outros tribunais: esta distribuição só tem o perfil do TRF2.
  - NÃO usar para decidir o mérito.
</quando_usar>

<instrucoes>
  <passo numero="1" nome="Conferir o tribunal">
    Ler o número CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO). Exigir J=4 e TR=02. CRITÉRIO DE PARADA: outro
    segmento → parar e informar que esta distribuição atende apenas o TRF2.
  </passo>
  <passo numero="2" nome="Carregar o perfil">
    Ler references/perfil-trf2.md (campos fixos: codigo_cnj, sede_estados, sistema_processual,
    download_automatico, mcp_jurisprudencia, proveniencia_adaptador, formato_ementa, regimento).
    CRITÉRIO DE PARADA: campo ausente vira [LACUNA: campo].
  </passo>
  <passo numero="3" nome="Formato da ementa">
    Quando a etapa for de redação de ementa, ler references/formato-ementa.md.
  </passo>
  <passo numero="4" nome="Respeitar o que está A CONFERIR">
    Itens marcados "A CONFERIR" ou "A CONFERIR NO REGIMENTO" nunca são preenchidos de memória: vão
    como [VERIFICAR] na análise e para a prancha de conferência humana.
  </passo>
</instrucoes>

<conhecimento>
  - MCP de jurisprudência: trf2-eproc (portal de jurisprudência eProc do TRF2), registrado no
    .mcp.json do projeto. Sintaxe: termo ou nao prox "frase" *wildcard (case-insensitive).
  - Precedentes vinculantes STF/STJ: bnp-api (Banco Nacional de Precedentes), também no .mcp.json.
  - Proveniência: o gate de reauditoria tem adaptador para bnp-api; resultados do trf2-eproc recebem
    SEM_ADAPTADOR e vão à prancha de conferência humana, nunca como CONFIRMADA.
  - Download automático: não há. O usuário fornece o PDF/TXT dos autos, baixado do eProc.
</conhecimento>

<restricoes>
  - Preencher de memória item marcado A CONFERIR
  - Hardcodar caminho absoluto ou nome de MCP fora do perfil
  - Tratar fonte SEM_ADAPTADOR como confirmada
</restricoes>

<referencias>
  - references/perfil-trf2.md: perfil do TRF2 (campos fixos).
  - references/formato-ementa.md: regras da ementa estruturada do CNJ, sem markdown.
</referencias>
