# -*- coding: utf-8 -*-
"""
MCP Server: TRF2 eProc - Jurisprudencia

Acesso a jurisprudencia do Tribunal Regional Federal da 2a Regiao (TRF2)
via sistema eProc (pagina publica). Endpoint aberto, sem autenticacao e sem captcha.
Cobre RJ e ES.

Bases (origem): TRF2, TRU2 (Turma Regional de Uniformizacao), Turmas Recursais.

Sintaxe de busca (case-insensitive, acentos ignorados) -- provada por count-oracle:
  - AND: implicito (espaco entre termos) ou 'e'. Ex: vacina responsabilidade
  - OR: ou. Ex: vacina ou aposentadoria
  - NOT: nao (com ou sem acento). Ex: vacina nao responsabilidade
  - Frase exata: "...". Ex: "faixa de fronteira"
  - Proximidade: prox. Ex: aposentadoria prox contribuicao
  - Wildcard: * (prefixo, sufixo ou ambos). Ex: penhor* ou *penhor*

Ref: engenharia-reversa.md (14/07/2026). Mesma familia do trf4-eproc/tjsc-eproc.
"""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import httpx
import re

mcp = FastMCP("trf2_eproc_mcp")

# ============================================================
# CONFIGURACAO
# ============================================================

HOST = "https://eproc.trf2.jus.br"
BASE_URL = f"{HOST}/eproc/externo_controlador.php"
PESQUISAR_URL = f"{BASE_URL}?acao=jurisprudencia@jurisprudencia/pesquisar"
SEARCH_URL = f"{BASE_URL}?acao=jurisprudencia@jurisprudencia/listar_resultados"
PAGINATE_URL = f"{BASE_URL}?acao=jurisprudencia@jurisprudencia/ajax_paginar_resultado"
INTEIRO_TEOR_URL = f"{BASE_URL}?acao=jurisprudencia@jurisprudencia/download_inteiro_teor"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": HOST,
    "Referer": SEARCH_URL,
}

AJAX_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": HOST,
    "Referer": SEARCH_URL,
}

# Vocabularios provados (engenharia-reversa.md secao 4)
ORIGENS = {
    "trf2": "1",
    "tru2": "2",
    "turmas_recursais": "3",
}

TIPOS_DOCUMENTO = {
    "acordaos": "1",
    "decisoes_monocraticas": "2",
    "sumulas": "3",           # base medida vazia sob origem TRF2 (ver dossie secao 8)
    "despachos_vice": "4",
}

ORDENACAO = {
    "mais_recentes": "1",
    "mais_antigos": "2",
}

# rdoCampo: I=Inteiro Teor, E=Ementa. Caput = E + chkCaput=on (campo logico "C").
CAMPOS_BUSCA = {"I", "E", "C"}


# ============================================================
# FUNCOES AUXILIARES
# ============================================================

def _limpar_html(texto: str) -> str:
    """Remove tags HTML (inclusive o realce <B><FONT>) e normaliza espacos."""
    if not texto:
        return ""
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def _truncar_texto(texto: str, max_chars: int = 6000) -> str:
    """Trunca texto preservando fim de frase."""
    if not texto or len(texto) <= max_chars:
        return texto
    texto_truncado = texto[:max_chars]
    ultimo_ponto = texto_truncado.rfind('.')
    if ultimo_ponto > max_chars * 0.8:
        texto_truncado = texto_truncado[:ultimo_ponto + 1]
    return texto_truncado + " [...]"


SIGLA = "TRF2"                 # sigla p/ referencia sintetizada no modo conciso
RESUMO_MAX_CHARS = 700         # tamanho do <ementa_resumo> no modo conciso


def _referencia_compacta(r: Dict[str, Any]) -> str:
    """Linha de referencia enxuta a partir dos campos ja extraidos (modo conciso).
    Substitui a <citacao> verbatim (que reproduz a ementa inteira) por uma cabeca
    padronizada, evitando duplicar o texto ja presente no resumo."""
    seg: List[str] = [SIGLA]
    proc = " ".join(x for x in (r.get("classe", ""), r.get("numero", "")) if x).strip()
    if proc:
        seg.append(proc)
    if r.get("orgao"):
        seg.append(r["orgao"])
    if r.get("relator"):
        seg.append(f"Rel. {r['relator']}")
    if r.get("data_julgamento"):
        seg.append(f"j. {r['data_julgamento']}")
    return ", ".join(seg)


def _escape_xml(texto: str) -> str:
    """Escapa caracteres especiais para XML."""
    if not texto:
        return ""
    texto = str(texto)
    texto = texto.replace("&", "&amp;")
    texto = texto.replace("<", "&lt;")
    texto = texto.replace(">", "&gt;")
    texto = texto.replace('"', "&quot;")
    return texto


def _extrair_total(html: str) -> int:
    """
    Total de resultados: <h2> 'N documentos encontrados' (sempre presente, inclusive 0);
    fallback para o hidden hdnTotalResultado (que traz 'type="hidden"' ENTRE name e value
    e some na pagina de 0 resultados).
    """
    m = re.search(r'(\d+)\s*documentos?\s*encontrado', html, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'id="hdnTotalResultado"[^>]*value="(\d+)"', html)
    return int(m.group(1)) if m else 0


def _extrair_resultados(html: str) -> List[Dict[str, Any]]:
    """Extrai resultados do HTML retornado pelo eProc TRF2."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(".resultadoItem")
    resultados: List[Dict[str, Any]] = []

    for item in items:
        record: Dict[str, Any] = {}

        item_id = (item.get("id") or "").replace("resultado", "")
        if item_id:
            record["id"] = item_id
            record["inteiro_teor"] = f"{INTEIRO_TEOR_URL}&id_jurisprudencia={item_id}"

        tipo_el = item.select_one(".resValueTipoJurisprudencia")
        if tipo_el:
            record["tipo"] = tipo_el.get_text(strip=True)

        num_el = item.select_one("a.numero-processo")
        if num_el:
            record["numero"] = num_el.get_text(strip=True)

        cit_el = item.select_one("a.copiarCitacao")
        if cit_el and cit_el.get("data-citacao"):
            record["citacao"] = _limpar_html(cit_el["data-citacao"])

        for label in item.select(".resLabel"):
            key = label.get_text(strip=True)
            value_el = label.find_next_sibling(class_="resValue")
            if not value_el:
                continue
            value = value_el.get_text(" ", strip=True)

            if key == "PROCESSO":
                span = value_el.select_one("span")
                if span:
                    record["classe"] = span.get_text(strip=True)
            elif key == "UF":
                record["uf"] = value
            elif key == "ÓRGÃO JULGADOR":
                record["orgao"] = value
            elif key == "DATA DO JULGAMENTO":
                record["data_julgamento"] = value
            elif key == "DATA DA PUBLICAÇÃO":
                record["data_publicacao"] = value
            elif key == "RELATOR":
                record["relator"] = value
            elif key == "EMENTA":
                record["ementa"] = _limpar_html(value)
            elif key == "DECISÃO":
                record["decisao"] = _limpar_html(value)

        record["conteudo"] = record.get("ementa") or record.get("decisao") or ""
        record["conteudo_tipo"] = "Ementa" if record.get("ementa") else (
            "Decisão" if record.get("decisao") else "Conteúdo")

        resultados.append(record)

    return resultados


def _montar_form(
    busca: str,
    page_size: int,
    origem: Optional[str],
    tipo_documento: Optional[str],
    campo: str,
    ordenacao: str,
    data_decisao_inicio: Optional[str],
    data_decisao_fim: Optional[str],
    data_publicacao_inicio: Optional[str],
    data_publicacao_fim: Optional[str],
    processo: Optional[str],
    classe_processual: Optional[str],
    orgao_julgador: Optional[str],
    relator: Optional[str],
    precedente_relevante: bool,
    agrupar_resultados: bool,
    pagina: int,
) -> List[tuple]:
    """Monta a lista ordenada de campos do formulario (multi usa sufixo [])."""
    campo_real = "E" if campo == "C" else campo  # caput usa E + chkCaput
    fields: List[tuple] = [("txtPesquisa", busca)]

    origem_val = ORIGENS.get(origem, "1") if origem else "1"
    fields.append(("selOrigem[]", origem_val))

    if tipo_documento:
        tipo_val = TIPOS_DOCUMENTO.get(tipo_documento, tipo_documento)
        fields.append(("selTipoDocumento[]", tipo_val))

    fields.append(("rdoCampo", campo_real))
    if campo == "C":
        fields.append(("chkCaput", "on"))
    if agrupar_resultados:
        fields.append(("chkAgruparResultados", "on"))
    if precedente_relevante:
        fields.append(("chkPrecedenteRelevante", "on"))

    fields.append(("selOrdenacao", ordenacao))

    if data_decisao_inicio:
        fields.append(("dtDecisaoInicio", data_decisao_inicio))
    if data_decisao_fim:
        fields.append(("dtDecisaoFim", data_decisao_fim))
    if data_publicacao_inicio:
        fields.append(("dtPublicacaoInicio", data_publicacao_inicio))
    if data_publicacao_fim:
        fields.append(("dtPublicacaoFim", data_publicacao_fim))
    if processo:
        fields.append(("txtProcesso", processo))
    if classe_processual:
        fields.append(("selClasse[]", classe_processual))
    if orgao_julgador:
        fields.append(("selOrgao[]", orgao_julgador))
    if relator:
        fields.append(("selRelator[]", relator))

    fields.append(("selTamanhoPagina", str(page_size)))
    fields.append(("hdnPaginaAtual", str(pagina)))
    return fields


def _handle_error(e: Exception) -> str:
    """Formatacao consistente de erros."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Erro: Recurso nao encontrado."
        elif status == 403:
            return "Erro: Acesso negado."
        elif status == 429:
            return "Erro: Limite de requisicoes excedido. Aguarde."
        elif status >= 500:
            return f"Erro: Servidor indisponivel (HTTP {status})"
        return f"Erro: Falha na requisicao (HTTP {status})"
    elif isinstance(e, httpx.TimeoutException):
        return "Erro: Timeout na requisicao. Tente novamente."
    elif isinstance(e, httpx.ConnectError):
        return "Erro: Nao foi possivel conectar ao TRF2."
    return f"Erro: {type(e).__name__}: {str(e)}"


async def _fazer_busca(
    busca: str,
    max_resultados: int = 30,
    origem: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    campo: str = "E",
    ordenacao: str = "1",
    data_decisao_inicio: Optional[str] = None,
    data_decisao_fim: Optional[str] = None,
    data_publicacao_inicio: Optional[str] = None,
    data_publicacao_fim: Optional[str] = None,
    processo: Optional[str] = None,
    classe_processual: Optional[str] = None,
    orgao_julgador: Optional[str] = None,
    relator: Optional[str] = None,
    precedente_relevante: bool = False,
    agrupar_resultados: bool = False,
) -> tuple[List[Dict[str, Any]], int]:
    """Executa a busca e retorna (resultados, total). Corpo em iso-8859-1."""
    page_size = min(max(max_resultados, 1), 100)

    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
        # Semeia sessao (PHPSESSID) pela pagina de pesquisa
        await client.get(PESQUISAR_URL, headers={"User-Agent": USER_AGENT})

        fields = _montar_form(
            busca=busca, page_size=page_size, origem=origem,
            tipo_documento=tipo_documento, campo=campo, ordenacao=ordenacao,
            data_decisao_inicio=data_decisao_inicio, data_decisao_fim=data_decisao_fim,
            data_publicacao_inicio=data_publicacao_inicio,
            data_publicacao_fim=data_publicacao_fim, processo=processo,
            classe_processual=classe_processual, orgao_julgador=orgao_julgador,
            relator=relator, precedente_relevante=precedente_relevante,
            agrupar_resultados=agrupar_resultados, pagina=1,
        )
        body = urlencode(fields, encoding="iso-8859-1")
        resp = await client.post(SEARCH_URL, headers=HEADERS, content=body)
        resp.encoding = "iso-8859-1"
        resp.raise_for_status()

        html = resp.text
        total = _extrair_total(html)
        resultados = _extrair_resultados(html)

        # Paginacao: re-POST do form (pagina N) ate atingir max_resultados
        cookies = dict(resp.cookies)
        pagina = 1
        while len(resultados) < max_resultados and len(resultados) < total:
            pagina += 1
            pag_fields = _montar_form(
                busca=busca, page_size=page_size, origem=origem,
                tipo_documento=tipo_documento, campo=campo, ordenacao=ordenacao,
                data_decisao_inicio=data_decisao_inicio,
                data_decisao_fim=data_decisao_fim,
                data_publicacao_inicio=data_publicacao_inicio,
                data_publicacao_fim=data_publicacao_fim, processo=processo,
                classe_processual=classe_processual, orgao_julgador=orgao_julgador,
                relator=relator, precedente_relevante=precedente_relevante,
                agrupar_resultados=agrupar_resultados, pagina=pagina,
            )
            pag_body = urlencode(pag_fields, encoding="iso-8859-1")
            pag_resp = await client.post(
                PAGINATE_URL, headers=AJAX_HEADERS, content=pag_body, cookies=cookies
            )
            pag_resp.encoding = "iso-8859-1"
            if pag_resp.status_code != 200:
                break
            novos = _extrair_resultados(pag_resp.text)
            if not novos:
                break
            resultados.extend(novos)

    return resultados[:max_resultados], total


def _formatar_xml(resultados: List[Dict[str, Any]], total: int,
                  formato: str = "conciso") -> str:
    """Formata resultados em XML estruturado.

    formato="conciso" (padrao): metadados + <ementa_resumo> (~700 chars) + <citacao>
      compacta + <fonte>. Enxuto para triagem; NAO estoura o limite de token.
    formato="completo": ementa integral (integral, sem truncamento) em <conteudo> + <citacao>
      verbatim. Para lastro; para o inteiro teor use o link em <fonte>.
    """
    if not resultados:
        return (f'<jurisprudencia_trf2 total="0" retornados="0" formato="{formato}">\n'
                "  <mensagem>Nenhum resultado encontrado.</mensagem>\n"
                "</jurisprudencia_trf2>")

    linhas = [f'<jurisprudencia_trf2 total="{total}" retornados="{len(resultados)}" '
              f'formato="{formato}">']
    for i, r in enumerate(resultados, 1):
        linhas.append(f'  <item indice="{i}">')
        if r.get("tipo"):
            linhas.append(f'    <tipo>{_escape_xml(r["tipo"])}</tipo>')
        if r.get("numero"):
            linhas.append(f'    <numero>{_escape_xml(r["numero"])}</numero>')
        if r.get("classe"):
            linhas.append(f'    <classe>{_escape_xml(r["classe"])}</classe>')
        if r.get("uf"):
            linhas.append(f'    <uf>{_escape_xml(r["uf"])}</uf>')
        if r.get("orgao"):
            linhas.append(f'    <orgao>{_escape_xml(r["orgao"])}</orgao>')
        if r.get("relator"):
            linhas.append(f'    <relator>{_escape_xml(r["relator"])}</relator>')
        if r.get("data_julgamento"):
            linhas.append(f'    <data_julgamento>{_escape_xml(r["data_julgamento"])}</data_julgamento>')
        if r.get("data_publicacao"):
            linhas.append(f'    <data_publicacao>{_escape_xml(r["data_publicacao"])}</data_publicacao>')

        if formato == "completo":
            conteudo = r.get("conteudo", "")  # completo: sem truncar (lastro verbatim)
            if conteudo:
                linhas.append(f'    <conteudo tipo="{_escape_xml(r.get("conteudo_tipo","Conteúdo"))}">')
                linhas.append(f"      {_escape_xml(conteudo)}")
                linhas.append("    </conteudo>")
            if r.get("citacao"):
                linhas.append(f'    <citacao>{_escape_xml(r["citacao"])}</citacao>')
        else:
            resumo = _truncar_texto(r.get("conteudo", ""), RESUMO_MAX_CHARS)
            if resumo:
                linhas.append(
                    f'    <ementa_resumo tipo="{_escape_xml(r.get("conteudo_tipo","Conteúdo"))}">'
                    f'{_escape_xml(resumo)}</ementa_resumo>')
            linhas.append(f'    <citacao>{_escape_xml(_referencia_compacta(r))}</citacao>')

        if r.get("inteiro_teor"):
            linhas.append(f'    <fonte>{_escape_xml(r["inteiro_teor"])}</fonte>')

        linhas.append("  </item>")
    linhas.append("</jurisprudencia_trf2>")
    return "\n".join(linhas)


# ============================================================
# PYDANTIC MODELS
# ============================================================

class BuscaInput(BaseModel):
    """Input para busca de jurisprudencia no TRF2."""
    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra='forbid'
    )

    busca: str = Field(
        ...,
        description=(
            "Query com sintaxe do TRF2 eProc (case-insensitive, acentos ignorados). "
            "Operadores: AND (espaco implicito ou 'e'), ou (OR), nao/não (NOT), "
            '"..." (frase exata), prox (proximidade), * (wildcard prefixo/sufixo). '
            'Exemplos: "faixa de fronteira", vacina nao responsabilidade, penhor*'
        ),
        min_length=2, max_length=500,
    )
    max_resultados: int = Field(default=30, description="Maximo de resultados (1-100)", ge=1, le=100)
    formato: Optional[str] = Field(
        default="conciso",
        description=(
            "Volume por item: 'conciso' (padrao) = metadados + resumo da ementa "
            "(~700 chars) + citacao compacta + link, ideal para triagem e sem estourar "
            "o limite de token; 'completo' = ementa integral (integral, sem truncamento) + citacao "
            "verbatim, para lastro. Para o inteiro teor use o link <fonte>."
        ),
    )
    origem: Optional[str] = Field(
        default=None,
        description="Base: trf2 (padrao), tru2, turmas_recursais",
    )
    tipo_documento: Optional[str] = Field(
        default=None,
        description="Tipo: acordaos, decisoes_monocraticas, sumulas, despachos_vice",
    )
    campo: Optional[str] = Field(
        default="E",
        description="Onde buscar: E=Ementa (padrao), I=Inteiro Teor, C=Caput da Ementa",
    )
    ordenacao: Optional[str] = Field(
        default="1", description="Ordenacao: 1=mais recentes (padrao), 2=mais antigos"
    )
    data_inicio: Optional[str] = Field(default=None, description="Data julgamento inicio (DD/MM/AAAA)")
    data_fim: Optional[str] = Field(default=None, description="Data julgamento fim (DD/MM/AAAA)")
    data_publicacao_inicio: Optional[str] = Field(default=None, description="Data publicacao inicio (DD/MM/AAAA)")
    data_publicacao_fim: Optional[str] = Field(default=None, description="Data publicacao fim (DD/MM/AAAA)")
    processo: Optional[str] = Field(default=None, description="Numero do processo (com ou sem mascara)")
    classe_processual: Optional[str] = Field(
        default=None,
        description="Classe processual: string EXATA do vocabulario (ver listar_filtros_trf2). Ex: 'Agravo de Instrumento'",
    )
    orgao_julgador: Optional[str] = Field(
        default=None,
        description="Orgao julgador: string EXATA do vocabulario. Ex: '1ª TURMA ESPECIALIZADA'",
    )
    relator: Optional[str] = Field(
        default=None,
        description="Relator/Relatora: string EXATA do vocabulario (nome em MAIUSCULAS)",
    )
    precedente_relevante: bool = Field(
        default=False,
        description="Apenas precedentes relevantes (acervo de jurisprudencia selecionada do CJF)",
    )
    agrupar_resultados: bool = Field(
        default=False,
        description="Agrupar resultados semelhantes (mesma relatoria/classe/ementa), exibindo o mais atual",
    )

    @field_validator('busca')
    @classmethod
    def validar_busca(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Termo de busca nao pode ser vazio")
        return v.strip()

    @field_validator('campo')
    @classmethod
    def validar_campo(cls, v: Optional[str]) -> str:
        v = (v or "E").upper()
        if v not in CAMPOS_BUSCA:
            raise ValueError("campo deve ser I (inteiro teor), E (ementa) ou C (caput)")
        return v

    @field_validator('formato')
    @classmethod
    def validar_formato(cls, v: Optional[str]) -> str:
        v = (v or "conciso").lower()
        if v not in ("conciso", "completo"):
            raise ValueError("formato deve ser 'conciso' ou 'completo'")
        return v


class RelatorioInput(BaseModel):
    """Input para geracao de relatorio do TRF2."""
    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra='forbid'
    )

    busca: str = Field(
        ..., description="Query com sintaxe do TRF2 eProc (mesma de buscar_trf2).",
        min_length=2, max_length=500,
    )
    max_resultados: int = Field(default=10, description="Maximo de resultados (1-50)", ge=1, le=50)
    origem: Optional[str] = Field(default=None, description="Base: trf2 (padrao), tru2, turmas_recursais")
    tipo_documento: Optional[str] = Field(default=None, description="Tipo: acordaos, decisoes_monocraticas, sumulas, despachos_vice")
    campo: Optional[str] = Field(default="E", description="E=Ementa (padrao), I=Inteiro Teor, C=Caput")
    precedente_relevante: bool = Field(default=False, description="Apenas precedentes relevantes (CJF)")

    @field_validator('busca')
    @classmethod
    def validar_busca(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Termo de busca nao pode ser vazio")
        return v.strip()

    @field_validator('campo')
    @classmethod
    def validar_campo(cls, v: Optional[str]) -> str:
        v = (v or "E").upper()
        if v not in CAMPOS_BUSCA:
            raise ValueError("campo deve ser I, E ou C")
        return v


# ============================================================
# TOOLS
# ============================================================

@mcp.tool(
    name="buscar_trf2",
    annotations={
        "title": "Buscar Jurisprudencia no TRF2",
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def buscar_trf2(params: BuscaInput) -> str:
    """
    Busca jurisprudencia no Tribunal Regional Federal da 2a Regiao (TRF2)
    via sistema eProc (pagina publica, sem login). Cobre RJ e ES.

    SINTAXE DE BUSCA (case-insensitive, acentos ignorados) -- provada por count-oracle:
    | Operador    | Sintaxe      | Exemplo                          |
    |-------------|--------------|----------------------------------|
    | AND         | (espaco)/e   | vacina responsabilidade          |
    | OR          | ou           | vacina ou aposentadoria          |
    | NOT         | nao / não    | vacina nao responsabilidade      |
    | Frase exata | "..."        | "faixa de fronteira"             |
    | Proximidade | prox         | aposentadoria prox contribuicao  |
    | Wildcard    | *            | penhor* (sufixo) ou *penhor*     |

    FILTROS (provados por sonda diferencial; ver engenharia-reversa.md):
    - origem: trf2 (padrao), tru2, turmas_recursais
    - tipo_documento: acordaos, decisoes_monocraticas, sumulas, despachos_vice
      (obs: a base de sumulas do TRF2 estava vazia na medicao; monocraticas/vice nao tem
      ementa -> use campo="I" para busca-las)
    - campo: E (ementa, padrao), I (inteiro teor), C (caput da ementa)
    - ordenacao: 1 (mais recentes), 2 (mais antigos)
    - data_inicio/data_fim: DD/MM/AAAA (julgamento)
    - data_publicacao_inicio/data_publicacao_fim: DD/MM/AAAA
    - processo: numero do processo
    - classe_processual, orgao_julgador, relator: string EXATA do vocabulario
    - precedente_relevante: true para acervo selecionado do CJF
    - agrupar_resultados: true para agrupar semelhantes
    - formato: "conciso" (PADRAO) devolve por item metadados + <ementa_resumo> (~700
      chars) + <citacao> compacta + <fonte> — ideal para TRIAGEM e nao estoura o limite
      de token. "completo" devolve a ementa integral (integral, sem truncamento) + <citacao>
      verbatim — use para LASTRO. Para o inteiro teor, siga o link em <fonte>.

    Returns:
        str: XML <jurisprudencia_trf2 total=".." retornados=".." formato="..">.
    """
    try:
        resultados, total = await _fazer_busca(
            busca=params.busca, max_resultados=params.max_resultados,
            origem=params.origem, tipo_documento=params.tipo_documento,
            campo=params.campo or "E", ordenacao=params.ordenacao or "1",
            data_decisao_inicio=params.data_inicio, data_decisao_fim=params.data_fim,
            data_publicacao_inicio=params.data_publicacao_inicio,
            data_publicacao_fim=params.data_publicacao_fim, processo=params.processo,
            classe_processual=params.classe_processual,
            orgao_julgador=params.orgao_julgador, relator=params.relator,
            precedente_relevante=params.precedente_relevante,
            agrupar_resultados=params.agrupar_resultados,
        )
        formato = params.formato or "conciso"
        xml = _formatar_xml(resultados, total, formato)
        meta = (f'<!-- Busca: "{params.busca}" | Total: {total} | '
                f'Retornados: {len(resultados)} | Formato: {formato} -->\n')
        return meta + xml
    except Exception as e:
        return f"<erro>{_handle_error(e)}</erro>"


@mcp.tool(
    name="gerar_relatorio_trf2",
    annotations={
        "title": "Gerar Relatorio de Jurisprudencia do TRF2",
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def gerar_relatorio_trf2(params: RelatorioInput) -> str:
    """
    Busca jurisprudencia no TRF2 e gera relatorio formatado em Markdown.

    USE ESTA TOOL para um relatorio de apresentacao. Para analise programatica,
    prefira buscar_trf2 (XML). A sintaxe e a MESMA de buscar_trf2.

    Returns:
        str: Relatorio em Markdown.
    """
    try:
        resultados, total = await _fazer_busca(
            busca=params.busca, max_resultados=params.max_resultados,
            origem=params.origem, tipo_documento=params.tipo_documento,
            campo=params.campo or "E", precedente_relevante=params.precedente_relevante,
        )
        data_hora = datetime.now().strftime("%d/%m/%Y as %H:%M")
        linhas = [
            "# Relatorio de Jurisprudencia - TRF2 (eProc)",
            "",
            f"**Busca realizada:** `{params.busca}`",
            f"**Data/Hora:** {data_hora}",
            f"**Documentos encontrados:** {total}",
            f"**Documentos exibidos:** {len(resultados)}",
            "",
            "---",
            "",
        ]
        if not resultados:
            linhas.append("*Nenhum documento encontrado.*")
            return "\n".join(linhas)

        for i, r in enumerate(resultados, 1):
            numero = r.get("numero", "N/I")
            classe = r.get("classe", "")
            titulo = numero + (f" ({classe})" if classe else "")
            linhas.extend([f"## {i}. {titulo}", ""])
            if r.get("tipo"):
                linhas.append(f"**Tipo:** {r['tipo']}")
            linhas.append(f"**Relator:** {r.get('relator', 'N/I')}")
            if r.get("orgao"):
                linhas.append(f"**Orgao Julgador:** {r['orgao']}")
            if r.get("uf"):
                linhas.append(f"**UF:** {r['uf']}")
            if r.get("data_julgamento"):
                linhas.append(f"**Data Julgamento:** {r['data_julgamento']}")
            if r.get("data_publicacao"):
                linhas.append(f"**Data Publicacao:** {r['data_publicacao']}")
            linhas.append("")

            conteudo = _truncar_texto(r.get("conteudo", ""), 3000)
            if conteudo:
                linhas.extend([f"### {r.get('conteudo_tipo', 'Conteudo')}", "", f"> {conteudo}", ""])
            if r.get("citacao"):
                linhas.extend([f"**Citacao:** {r['citacao']}", ""])
            if r.get("inteiro_teor"):
                linhas.extend([f"**Inteiro teor:** {r['inteiro_teor']}", ""])
            linhas.extend(["---", ""])

        linhas.extend(["", f"*Relatorio gerado via MCP TRF2 eProc em {data_hora}*"])
        return "\n".join(linhas)
    except Exception as e:
        return f"**Erro:** {_handle_error(e)}"


@mcp.tool(
    name="listar_filtros_trf2",
    annotations={
        "title": "Listar Filtros Disponiveis no TRF2",
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False,
    },
)
async def listar_filtros_trf2() -> str:
    """
    Lista operadores, filtros e vocabularios disponiveis para busca no TRF2 eProc.

    Os vocabularios de classe_processual, orgao_julgador e relator sao extensos e
    ficam pre-carregados nos <select> selClasse/selOrgao/selRelator da pagina de
    pesquisa (150 classes, 52 orgaos, 118 relatores). Passe a string EXATA do valor.

    Returns:
        str: XML estruturado com filtros e operadores.
    """
    linhas = ['<filtros_trf2>']

    linhas.append('  <operadores nota="Case-insensitive. Acentos ignorados. Provados por count-oracle.">')
    linhas.append('    <operador sintaxe="(espaco) / e">AND. Ex: vacina responsabilidade</operador>')
    linhas.append('    <operador sintaxe="ou">OR. Ex: vacina ou aposentadoria</operador>')
    linhas.append('    <operador sintaxe="nao">NOT (com ou sem acento). Ex: vacina nao responsabilidade</operador>')
    linhas.append('    <operador sintaxe="&quot;...&quot;">Frase exata. Ex: "faixa de fronteira"</operador>')
    linhas.append('    <operador sintaxe="prox">Proximidade (qualquer ordem). Ex: aposentadoria prox contribuicao</operador>')
    linhas.append('    <operador sintaxe="*">Wildcard prefixo/sufixo/ambos. Ex: penhor* ou *penhor*</operador>')
    linhas.append('  </operadores>')

    linhas.append('  <origem nota="Base pesquisavel (multipla)">')
    rotulos_origem = {"trf2": "TRF2", "tru2": "TRU2 (Turma Regional de Uniformizacao)",
                      "turmas_recursais": "Turmas Recursais"}
    for key, val in ORIGENS.items():
        linhas.append(f'    <opcao codigo="{key}" valor="{val}">{rotulos_origem[key]}</opcao>')
    linhas.append('  </origem>')

    linhas.append('  <tipo_documento>')
    rotulos_tipo = {"acordaos": "Acordao", "decisoes_monocraticas": "Decisao monocratica",
                    "sumulas": "Sumula", "despachos_vice": "Despacho/Decisao da Vice-Presidencia"}
    for key, val in TIPOS_DOCUMENTO.items():
        linhas.append(f'    <opcao codigo="{key}" valor="{val}">{rotulos_tipo[key]}</opcao>')
    linhas.append('    <nota>Base de sumulas medida VAZIA sob origem TRF2 (14/07/2026). '
                  'Monocraticas e despachos NAO tem ementa: use campo="I" (inteiro teor) para busca-los.</nota>')
    linhas.append('  </tipo_documento>')

    linhas.append('  <campo_busca>')
    linhas.append('    <opcao codigo="E">Ementa (padrao)</opcao>')
    linhas.append('    <opcao codigo="I">Inteiro Teor</opcao>')
    linhas.append('    <opcao codigo="C">Caput da Ementa</opcao>')
    linhas.append('  </campo_busca>')

    linhas.append('  <ordenacao>')
    linhas.append('    <opcao codigo="1">Mais recentes (padrao)</opcao>')
    linhas.append('    <opcao codigo="2">Mais antigos</opcao>')
    linhas.append('  </ordenacao>')

    linhas.append('  <datas formato="DD/MM/AAAA">')
    linhas.append('    <campo nome="data_inicio">Data julgamento inicio</campo>')
    linhas.append('    <campo nome="data_fim">Data julgamento fim</campo>')
    linhas.append('    <campo nome="data_publicacao_inicio">Data publicacao inicio</campo>')
    linhas.append('    <campo nome="data_publicacao_fim">Data publicacao fim</campo>')
    linhas.append('  </datas>')

    linhas.append('  <campos_especificos>')
    linhas.append('    <campo nome="processo">Numero do processo (com ou sem mascara)</campo>')
    linhas.append('    <campo nome="classe_processual" tipo="vocabulario">String EXATA. Ex: "Agravo de Instrumento", "Apelação Criminal"</campo>')
    linhas.append('    <campo nome="orgao_julgador" tipo="vocabulario">String EXATA. Ex: "1ª TURMA ESPECIALIZADA", "3A. SEÇÃO ESPECIALIZADA"</campo>')
    linhas.append('    <campo nome="relator" tipo="vocabulario">Nome EXATO em MAIUSCULAS. Ex: "ABEL FERNANDES GOMES"</campo>')
    linhas.append('    <nota>Vocabularios completos ficam nos &lt;select&gt; selClasse/selOrgao/selRelator da pagina '
                  'https://eproc.trf2.jus.br/eproc/externo_controlador.php?acao=jurisprudencia@jurisprudencia/pesquisar</nota>')
    linhas.append('  </campos_especificos>')

    linhas.append('  <opcoes_booleanas>')
    linhas.append('    <opcao nome="precedente_relevante">Apenas precedentes relevantes (acervo selecionado do CJF)</opcao>')
    linhas.append('    <opcao nome="agrupar_resultados">Agrupar semelhantes (mesma relatoria/classe/ementa)</opcao>')
    linhas.append('  </opcoes_booleanas>')

    linhas.append('</filtros_trf2>')
    return "\n".join(linhas)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    mcp.run()
