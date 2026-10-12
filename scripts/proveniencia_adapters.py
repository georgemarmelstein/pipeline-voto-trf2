#!/usr/bin/env python3
"""proveniencia_adapters.py - Receitas por dialeto para recuperar o texto oficial.

Importa os módulos dos servidores MCP locais (SDK oficial: @mcp.tool() devolve a
função original; todos têm guarda __main__) e chama as funções de busca
DIRETAMENTE — sem protocolo MCP, sem LLM. Cada adaptador devolve uma lista de
textos oficiais brutos (XML/strings das bases); o casamento do verbatim é do
chamador (proveniencia_core.casar_trecho). Receitas:

  bnp-api            identidade estruturada (nr + tipos + órgão) via parse_referencia
  julia-trf5         numero_processo (CNJ) + frase curta POR FRAGMENTO amostrado
  cjf-jurisprudencia DUAS janelas curtas e LITERALMENTE CONTÍGUAS (aspas = frase
                     exata; ao contrário de frase_de_busca, não pula stopwords no
                     meio) unidas por E, + filtro de tribunal; se campo != ementa
                     e houver id, baixa o documento
  tnu-eproc          frases curtas (dialeto eproc via portal TNU)
  pesquisa-stj       SEM adaptador local (conector remoto claude.ai) -> KeyError,
                     que o gate traduz para o estado SEM_ADAPTADOR
"""
import asyncio
import importlib.util
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proveniencia_core import STOPWORDS, fragmentar, frase_de_busca, parse_referencia

_BASE = os.environ.get("PROVENIENCIA_SERVERS_DIR",
                       os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    ".claude", "mcp-servers"))
SERVIDORES = {
    "bnp-api": os.path.join(_BASE, "bnp-api", "server.py"),
    "julia-trf5": os.path.join(_BASE, "julia-trf5", "server.py"),
    "cjf-jurisprudencia": os.path.join(_BASE, "cjf-jurisprudencia", "server.py"),
    "tnu-eproc": os.path.join(_BASE, "tnu-eproc", "server.py"),
}
_MODULOS = {}


class BaseIndisponivel(Exception):
    """Rede/base fora do ar ou resposta de erro do portal."""


def carregar_servidor(origem):
    if origem not in _MODULOS:
        caminho = SERVIDORES[origem]
        spec = importlib.util.spec_from_file_location(f"srv_{origem.replace('-', '_')}",
                                                      caminho)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODULOS[origem] = mod
    return _MODULOS[origem]


def _checar_erro(resposta):
    """Os servidores capturam exceções e devolvem strings de erro; traduzir
    para BaseIndisponivel. Heurística: tag/prefixo de erro no texto."""
    if not isinstance(resposta, str) or not resposta.strip():
        raise BaseIndisponivel("resposta vazia da base")
    baixa = resposta[:400].casefold()
    if "<erro" in baixa or "[erro]" in baixa or "timeout" in baixa \
            or "connecterror" in baixa or "erro de conexão" in baixa:
        raise BaseIndisponivel(resposta[:200])
    return resposta


def _frases(fonte, max_fragmentos):
    """Frases curtas de recuperação: amostra início/meio/fim dos fragmentos."""
    frags = fragmentar(fonte["trecho_verbatim"]) or [fonte["trecho_verbatim"]]
    if len(frags) > max_fragmentos:
        frags = [frags[0], frags[len(frags) // 2], frags[-1]]
    return ['"' + frase_de_busca(f) + '"' for f in frags]


def _oficial_bnp(fonte, max_fragmentos):
    mod = carregar_servidor("bnp-api")
    ident = parse_referencia(fonte)
    kwargs = {"busca": frase_de_busca(fonte["trecho_verbatim"], 4) or fonte["referencia"]}
    if ident["estrategia"] == "precedente":
        kwargs["nr"] = ident["nr"]
        kwargs["tipos"] = ident["tipos"]
        if fonte.get("tribunal"):
            kwargs["orgaos"] = [fonte["tribunal"]]
    try:
        resposta = asyncio.run(mod.buscar_precedentes(mod.BuscaInput(**kwargs)))
    except Exception as e:
        raise BaseIndisponivel(str(e))
    return [_checar_erro(resposta)]


_ORGAOS_G1 = {"JFCE", "JFPE", "JFPB", "JFRN", "JFAL", "JFSE"}


def _oficial_julia(fonte, max_fragmentos):
    """ATENÇÃO ao dialeto: o <conteudo> dos resultados de busca do JULIA é um
    SNIPPET truncado (~100 chars em volta do termo) — casar um trecho longo só
    contra snippets dá falso negativo. Receita: (1) buscar por numero_processo
    + frase curta (recuperação/identificação); (2) baixar o INTEIRO TEOR do
    processo (obter_inteiro_teor devolve Markdown com o texto integral dos
    documentos judiciais) e casar contra ele. Resposta "[VAZIO]" não é erro:
    vira casamento negativo (NAO_ENCONTRADA), que é a semântica correta.

    Instância/órgão da REVERIFICAÇÃO seguem o da FONTE, não um default fixo:
    fonte hardcoded em G2/TRF5 zera toda decisão de 1º grau (Seções Judiciárias
    JFCE/JFPE/JFPB/JFRN/JFAL/JFSE, instância G1) — bug descoberto 13/08/2026 no
    trilho pesquisador-george (cascata de 1º grau), onde a verificação nunca
    encontrava nada por buscar no órgão/instância errados."""
    mod = carregar_servidor("julia-trf5")
    ident = parse_referencia(fonte)
    cnj = ident.get("cnj", "")
    tribunal = (fonte.get("tribunal") or "").upper()
    if tribunal in _ORGAOS_G1:
        orgao, instancia = tribunal, "G1"
    else:
        orgao, instancia = "TRF5", "G2"
    frases = _frases(fonte, max_fragmentos)  # Calcula FORA da try para não mascarar KeyError
    textos = []
    try:
        for frase in frases:
            textos.append(_checar_erro(mod.buscar_julia(
                termo=frase, numero_processo=cnj, instancia=instancia,
                orgao=orgao, max_resultados=5)))
        if cnj:
            textos.append(_checar_erro(mod.obter_inteiro_teor(
                numero_processo=cnj, orgao=orgao, instancia=instancia,
                max_documentos=5)))
    except BaseIndisponivel:
        raise
    except Exception as e:
        raise BaseIndisponivel(str(e))
    return textos


def _frase_curta_cjf(fragmento, n_palavras=2):
    """Dialeto CJF: busca por frase exata (aspas) exige contiguidade LITERAL
    no texto original — frase_de_busca pula stopwords em TODO o fragmento e
    por isso concatena palavras que não são um trecho contíguo (validado ao
    vivo em 24/07/2026 contra o AG 1999.04.01.035314-4/TRF4: a frase antiga
    '"iminente cobrança tributo autoriza uso"' zera, itens=0). Aqui pulamos
    só as stopwords iniciais e devolvemos DUAS janelas curtas e literais
    (início e um pouco mais adiante do fragmento) unidas por E (AND) — a
    mesma consulta ao vivo confirma: '"iminente cobrança"' sozinha já isola
    o único acórdão (itens=1)."""
    palavras = [p for p in (re.sub(r"^\W+|\W+$", "", w) for w in fragmento.split()) if p]
    if not palavras:
        return '""'
    ini = next((i for i, p in enumerate(palavras) if p.casefold() not in STOPWORDS), 0)
    janela1 = " ".join(palavras[ini:ini + n_palavras]) or palavras[0]
    pos2 = ini + n_palavras + 2
    if pos2 + n_palavras > len(palavras):
        return f'"{janela1}"'
    janela2 = " ".join(palavras[pos2:pos2 + n_palavras])
    return f'"{janela1}" E "{janela2}"'


def _oficial_cjf(fonte, max_fragmentos):
    mod = carregar_servidor("cjf-jurisprudencia")
    tribunais = fonte.get("tribunal") or "STF,STJ,TNU,TRF1,TRF2,TRF3,TRF4,TRF5"
    frags = fragmentar(fonte["trecho_verbatim"]) or [fonte["trecho_verbatim"]]
    if len(frags) > max_fragmentos:
        frags = [frags[0], frags[len(frags) // 2], frags[-1]]
    frases = [_frase_curta_cjf(f) for f in frags]  # Calcula FORA da try para não mascarar KeyError
    textos = []
    try:
        for frase in frases:
            resposta = _checar_erro(mod.buscar_jurisprudencia_cjf(
                busca=frase, tribunais=tribunais, max_resultados=5))
            textos.append(resposta)
            if fonte.get("campo") not in (None, "ementa", "sumula", "tese"):
                for doc_id in re.findall(r'id="([A-Z]{3}\w+)"', resposta)[:2]:
                    try:
                        textos.append(_checar_erro(
                            mod.obter_documento_cjf(id_documento=doc_id, busca=frase,
                                                     tribunais=tribunais)))
                    except (BaseIndisponivel, TypeError) as e:
                        print(f"[AVISO] reforço obter_documento_cjf falhou ({e.__class__.__name__}): {e}", file=sys.stderr)
    except BaseIndisponivel:
        raise
    except Exception as e:
        raise BaseIndisponivel(str(e))
    return textos


def _oficial_tnu(fonte, max_fragmentos):
    mod = carregar_servidor("tnu-eproc")
    frases = _frases(fonte, max_fragmentos)  # Calcula FORA da try para não mascarar KeyError
    textos = []
    try:
        for frase in frases:
            textos.append(_checar_erro(mod.buscar_tnu(busca=frase, max_resultados=5)))
    except BaseIndisponivel:
        raise
    except Exception as e:
        raise BaseIndisponivel(str(e))
    return textos


ADAPTADORES = {"bnp-api": _oficial_bnp, "julia-trf5": _oficial_julia,
               "cjf-jurisprudencia": _oficial_cjf, "tnu-eproc": _oficial_tnu}


def obter_textos_oficiais(fonte, max_fragmentos=3):
    return ADAPTADORES[fonte["origem_mcp"]](fonte, max_fragmentos)
