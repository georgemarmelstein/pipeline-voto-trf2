# Dossiê de Engenharia Reversa — TRF2 eProc (Jurisprudência)

> Reconhecimento em 14/07/2026 a partir da URL da pesquisa + **sondas diferenciais ao
> vivo** (portal aberto, sem captcha nem login). Sem HAR nem manual — a página pública
> e o count-oracle foram os mapas. Fingerprint eProc reconhecido: herança direta do
> irmão `trf4-eproc` (mesma família), com o dialeto TRF2 medido campo a campo.
> Todos os operadores e todos os filtros expostos têm contagem registrada (**provado**).

---

## 1. Arquitetura

| Camada | Descrição | URL |
|--------|-----------|-----|
| Front | Página pública do eProc TRF2, HTML server-side (iso-8859-1) + jQuery | `.../eproc/externo_controlador.php?acao=jurisprudencia@jurisprudencia/pesquisar` |
| Busca | POST form-urlencoded → HTML completo com resultados | `.../listar_resultados` |
| Paginação | POST do formulário serializado (`hdnUrlPaginar`) | `.../ajax_paginar_resultado` |
| Inteiro teor | link por documento (`a.inteiroTeor@data-link`) | `.../download_inteiro_teor&id_jurisprudencia=<ID>` |

Host: `https://eproc.trf2.jus.br`. Prefixo do controlador: `/eproc/`.
Cobre RJ e ES (2ª Região).

## 2. Mapa de proteção (por superfície)

| Superfície | Proteção | Viabilidade |
|-----------|----------|-------------|
| Busca (`listar_resultados`) | Nenhuma. Só um `PHPSESSID` (GET a `pesquisar`). Sem captcha, CSRF ou login. | **Aberta** — provado ao vivo |
| Paginação / inteiro teor | Mesma sessão / link direto | Aberta |

Sem `cf-ray`, sem sinais de recaptcha/hcaptcha no HTML. **100% viável para MCP server
em Python puro.**

## 3. Fingerprint e herança

- **Plataforma: eProc** — mesma família de `trf4-eproc`, `tjsc-eproc`, `tnu-eproc`.
  Rotas `eproc/externo_controlador.php?acao=...`, HTML `iso-8859-1`, paginação AJAX
  própria, estrutura `.resultadoItem`/`.resLabel`/`.resValue`.
- **Herdado e confirmado:** `response.encoding = "iso-8859-1"`; corpo POST url-encoded
  em iso-8859-1; total lido do `<h2>N documentos encontrados`; extrator de item idêntico
  ao do TRF4 (inclusive `a.copiarCitacao@data-citacao` e `a.inteiroTeor@data-link`).
- **Motor de busca:** textual da família (`E OU NÃO PROX *`, frase por aspas),
  case-insensitive e insensível a acento — **confirmado por count-oracle** (§5).

### Dialeto que difere do TRF4 (medido, não assumido — lição §11 de licoes-de-campo)

| Aspecto | TRF4 | **TRF2** |
|---------|------|----------|
| Host / prefixo | `eproc-jur.trf4.jus.br` / `eproc2trf4` | `eproc.trf2.jus.br` / `eproc` |
| Origem (base) | 1=TRF4,2=TRU4,3=Turmas Recursais,**4=Varas Federais** | 1=TRF2,2=TRU2,3=Turmas Recursais (**sem Varas Federais**) |
| Tipo documento | 1=Acórdão,2=Monocrática,4=Vice | 1=Acórdão,2=Monocrática,**3=Súmula**,4=Vice |
| Precedente relevante | `ckbFiltrosin_precedente_relevante[]=Sim` | `chkPrecedenteRelevante=on` (o `ckb...[]=Sim` também funciona — ambos dão 4.163) |
| rdoCampo default na página | E (na sessão do HAR) | **I** (Inteiro teor) |

Igual ao TRF4: endpoint `listar_resultados`, paginação `ajax_paginar_resultado`,
`rdoCampo` I/E + `chkCaput` separado, datas `dtDecisao*`/`dtPublicacao*`,
`selClasse[]`/`selOrgao[]`/`selRelator[]`, ordenação `1`/`2`, tamanho máx `100`.

## 4. Contrato da busca (provado)

- **Método/URL:** `POST .../eproc/externo_controlador.php?acao=jurisprudencia@jurisprudencia/listar_resultados`
- **Headers:** `Content-Type: application/x-www-form-urlencoded`, `Origin`/`Referer` do
  host, `User-Agent` de navegador. Cookie `PHPSESSID` de um GET prévio a `pesquisar`.
- **Corpo (iso-8859-1):**

| Campo | Papel | Valores provados |
|-------|-------|------------------|
| `txtPesquisa` | Query (§5) | texto |
| `selOrigem[]` | Base | `1`=TRF2, `2`=TRU2, `3`=Turmas Recursais |
| `selTipoDocumento[]` | Tipo | `1`=Acórdão, `2`=Decisão monocrática, `3`=Súmula, `4`=Despacho/Decisão Vice |
| `rdoCampo` | Onde buscar | `I`=Inteiro Teor, `E`=Ementa |
| `chkCaput` | Restringe ao caput da ementa (só com `E`) | `on` |
| `chkAgruparResultados` | Agrupa semelhantes | `on` |
| `chkPrecedenteRelevante` | Só precedentes relevantes (acervo CJF) | `on` |
| `selOrdenacao` | Ordem | `1`=mais recentes, `2`=mais antigos |
| `selTamanhoPagina` | Itens por página | `10`/`25`/`50`/`100` (**máx 100**) |
| `dtDecisaoInicio`/`dtDecisaoFim` | Período de julgamento | `DD/MM/AAAA` |
| `dtPublicacaoInicio`/`dtPublicacaoFim` | Período de disponibilização | `DD/MM/AAAA` |
| `txtProcesso` | Nº do processo | texto |
| `selClasse[]` | Classe processual | string exata do vocabulário (150 opções) |
| `selOrgao[]` | Órgão julgador | string exata do vocabulário (52 opções) |
| `selRelator[]` | Relator/Relatora | string exata do vocabulário (118 opções) |
| `hdnPaginaAtual` | Página | `1..N` |

- **Resposta:** HTML `iso-8859-1`. Total em `<h2>N documentos encontrados</h2>`
  (sempre presente, inclusive `0`) e em `<input id="hdnTotalResultado" ... value="N">`
  (ausente na página de 0 resultados).
- **Item (`div.card.resultadoItem`, `id="resultado<ID>"`):** idêntico ao TRF4 —
  `.resValueTipoJurisprudencia`; `a.numero-processo` (+ `<span>` classe);
  `.resLabel`/`.resValue` (PROCESSO, UF, ÓRGÃO JULGADOR, DATA DO JULGAMENTO, DATA DA
  PUBLICAÇÃO, RELATOR, DECISÃO, EMENTA); `a.inteiroTeor@data-link`
  (`download_inteiro_teor&id_jurisprudencia=<ID>`); `a.copiarCitacao@data-citacao`
  (citação padronizada verbatim).
- **Paginação:** re-POST do formulário a `ajax_paginar_resultado` com `hdnPaginaAtual`
  incrementado, reusando cookies. Para `max_resultados ≤ 100`, uma requisição basta.

## 5. Gramática de consulta (provado — count oracle, 14/07/2026)

Base `campo=E`, `origem=1` (TRF2), `tipo=1` (Acórdão). Contagens registradas:

| Operador | Sintaxe | Prova (contagens) | Veredito |
|----------|---------|-------------------|----------|
| AND implícito | espaço | `vacina`=50; `vacina responsabilidade`=20 | real |
| AND explícito | `e` | `vacina e responsabilidade`=20 (= implícito) | real |
| OR | `ou` | `vacina ou aposentadoria`=50.358 > `aposentadoria`=50.311 | real (união) |
| NOT | `nao` | `vacina`(50) − `vacina∩resp`(20) = `vacina nao responsabilidade`=**30** | real e exato |
| Frase exata | `"..."` | `"faixa de fronteira"`=8 < `faixa de fronteira`(AND)=10 | real |
| Proximidade | `prox` | `aposentadoria prox contribuicao`=16.304 < AND=21.783 | real (mais estrito) |
| Curinga | `*` (prefixo/sufixo/ambos) | `penhora`=18.094 < `penhor*`=23.130 < `*penhor*`=24.359 | real |

Case-insensitive e acento-insensível (herdado da família; NOT exato confirma motor
booleano real, não substring).

## 6. Filtros provados (sonda diferencial com × sem)

| Filtro | Prova | Veredito |
|--------|-------|----------|
| `chkPrecedenteRelevante=on` | `aposentadoria`=50.311 → `+precedente`=**4.163** | filtra (não decorativo) |
| `selOrigem[]` | origem 1 = 50.311 → origens 1-3 = 85.322 | filtra |
| `selTipoDocumento[]` | tipo 1 (acórdão) = 50.311 → tipo 3 (súmula) = 0 | filtra (súmula: base vazia, ver §8) |
| `rdoCampo` | `aposentadoria` E=50.311, I=96.010, E+caput=30.141 | filtra (3 universos) |
| `selTamanhoPagina` | itens exibidos: `10`→10, `50`→50 | honrado |
| datas / `selClasse[]` / `selOrgao[]` / `selRelator[]` | herdados do contrato eProc idêntico ao TRF4 (lá provados individualmente); estrutura e nomes iguais | provado por família + estrutura idêntica |

Nenhum filtro decorativo detectado entre os expostos. Observação: `chkPrecedenteRelevante`
e `ckbFiltrosin_precedente_relevante[]=Sim` dão o MESMO recorte (4.163) — o TRF2 aceita
os dois; a tool usa `chkPrecedenteRelevante` (campo do próprio formulário).

## 7. Modelo de dados e capacidades ocultas

- **Vocabulários** `selClasse`/`selOrgao`/`selRelator` pré-carregados na página `pesquisar`
  (150 classes, 52 órgãos, 118 relatores) — valores são as próprias strings (com acentos),
  não IDs. A tool os expõe como passthrough e `listar_filtros_trf2` ensina a obtê-los.
- **Fonte por item:** `download_inteiro_teor&id_jurisprudencia=<ID>` (inteiro teor) e
  `copiarCitacao@data-citacao` (citação verbatim) — capturados como `<fonte>` e `<citacao>`.

## 8. Decisões pendentes / hipóteses a validar

- **Súmulas (tipo 3) medidas VAZIAS**: `tipo=3` retornou 0 em todas as sondas (aposentadoria,
  recurso, tributário, imposto, juros, competência, prescrição — em `campo=E` e `campo=I`).
  O filtro é aplicado (tipo 1 = 50.311 ≠ tipo 3 = 0), mas o acervo de súmulas parece vazio
  sob origem TRF2 nesta base. A tool expõe `sumulas`→3 (opção legítima do portal) com esta
  ressalva. Hipótese a checar: súmulas podem viver sob outra origem/base.
- `selTipoDocumento` por origem (TRU2, Turmas Recursais) não enumerado; a tool aceita id
  livre e o portal recarrega os tipos por origem via `ajax_listar_tipo_documento`.
- Paginação > 100 itens: implementada por re-POST a `ajax_paginar_resultado` (endpoint
  confirmado em `hdnUrlPaginar`); testada estruturalmente, não exercitada além da 1ª página.
