# MCP TRF2 eProc — Jurisprudência

Servidor MCP standalone para busca de jurisprudência do **Tribunal Regional Federal
da 2ª Região (TRF2)** via sistema **eProc** (página pública). Cobre RJ e ES.
Endpoint aberto — **sem login, sem captcha**.

Mesma família dos MCPs `trf4-eproc`, `tjsc-eproc` e `tnu-eproc` (plataforma eProc). O
reconhecimento completo (contrato, gramática e provas) está em
[`engenharia-reversa.md`](./engenharia-reversa.md).

## Bases pesquisáveis (origem)

| origem | Base |
|--------|------|
| `trf2` (padrão) | TRF2 (2º grau) |
| `tru2` | Turma Regional de Uniformização da 2ª Região |
| `turmas_recursais` | Turmas Recursais |

## Tools

| Tool | Retorno | Uso |
|------|---------|-----|
| `buscar_trf2` | XML `<jurisprudencia_trf2>` | Análise programática |
| `gerar_relatorio_trf2` | Markdown | Apresentação |
| `listar_filtros_trf2` | XML de filtros/operadores | Descoberta de parâmetros |

Cada item traz `<citacao>` (referência padronizada verbatim) e `<fonte>` (link do
inteiro teor) — prontos para lastro de citações no regime verbatim.

## Sintaxe de busca (provada por count-oracle)

Case-insensitive, acentos ignorados. Em `campo=E` (Ementa) por padrão.

| Operador | Sintaxe | Exemplo |
|----------|---------|---------|
| AND | espaço ou `e` | `vacina responsabilidade` |
| OR | `ou` | `vacina ou aposentadoria` |
| NOT | `nao` / `não` | `vacina nao responsabilidade` |
| Frase exata | `"..."` | `"faixa de fronteira"` |
| Proximidade | `prox` | `aposentadoria prox contribuicao` |
| Wildcard | `*` (prefixo/sufixo/ambos) | `penhor*`, `*penhor*` |

## Filtros

- `campo`: `E` (ementa, padrão), `I` (inteiro teor), `C` (caput da ementa)
- `tipo_documento`: `acordaos`, `decisoes_monocraticas`, `sumulas`, `despachos_vice`
  — **monocráticas/despachos não têm ementa**: use `campo="I"`. A base de **súmulas
  estava vazia** na medição (14/07/2026).
- `ordenacao`: `1` (mais recentes), `2` (mais antigos)
- `data_inicio`/`data_fim` e `data_publicacao_inicio`/`data_publicacao_fim` (DD/MM/AAAA)
- `processo`: número do processo (com ou sem máscara)
- `classe_processual`, `orgao_julgador`, `relator`: **string exata** do vocabulário
  (ver `listar_filtros_trf2`)
- `precedente_relevante`: só o acervo selecionado do CJF
- `agrupar_resultados`: agrupa semelhantes

## Instalação

```bash
pip install -r requirements.txt
```

## Registro no `.mcp.json` (raiz do projeto)

```json
{
  "mcpServers": {
    "trf2-eproc": {
      "command": "python",
      "args": ["C:\\Users\\georg\\superjurista\\.claude\\mcp-servers\\trf2-eproc\\server.py"]
    }
  }
}
```

O servidor só carrega em **sessão nova** do Claude Code.

## Exemplos

```
buscar_trf2(busca='"faixa de fronteira"', max_resultados=10)
buscar_trf2(busca="vacina nao responsabilidade", campo="I")
buscar_trf2(busca="aposentadoria", orgao_julgador="1ª TURMA ESPECIALIZADA")
buscar_trf2(busca="tributário", precedente_relevante=True)
gerar_relatorio_trf2(busca="responsabilidade civil do estado", max_resultados=5)
```

## Notas técnicas

- Respostas e corpo do POST em `iso-8859-1` (charset legado do eProc) — encoding fixado.
- Busca implementada uma única vez em `_fazer_busca()`, compartilhada pelas tools.
- Total lido do `<h2>N documentos encontrados</h2>` (sempre presente, inclusive `0`).
- Paginação por re-POST a `ajax_paginar_resultado`; para `max_resultados ≤ 100`, uma
  única requisição basta (máx 100/página).
