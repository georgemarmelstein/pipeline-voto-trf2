#!/usr/bin/env python3
"""proveniencia_core.py - Núcleo puro da cadeia de custódia de fontes (spec 24/07/2026).

Princípio (lição do falso negativo CJF de 24/07): a busca da base é só RECUPERAÇÃO;
o JULGAMENTO do verbatim é sempre local — `casar_trecho` contra o texto oficial
retornado, com a normalização canônica dos gates. Sem rede neste módulo.
"""
import html
import re
import unicodedata

CONFIRMADA = "CONFIRMADA"
NAO_ENCONTRADA = "NAO_ENCONTRADA"
BASE_INDISPONIVEL = "BASE_INDISPONIVEL"
SEM_ADAPTADOR = "SEM_ADAPTADOR"

RE_CNJ = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")
RE_CORTE = re.compile(r"\(\s*\.\.\.\s*\)|\[\s*\.\.\.\s*\]|\(\s*…\s*\)|\[\s*…\s*\]|…|\.\.\.")
RE_TEMA = re.compile(r"(?i)^tema(?:\s+repetitivo)?(?:\s+(?:rg|rr|irdr|iac|sirdr|irr))?\s+n?[ºo°.]?\s*([\d.]+)\b")
RE_SV = re.compile(r"(?i)^(?:sv|s[úu]mula\s+vinculante)\s+n?[ºo°.]?\s*([\d.]+)\b")
RE_SUM = re.compile(r"(?i)^s[úu]mula\s+n?[ºo°.]?\s*([\d.]+)\b")
RE_CC = re.compile(r"(?i)^(adi|adc|adpf|ado)\s+n?[ºo°.]?\s*([\d.]+)$")

STOPWORDS = {"a", "o", "as", "os", "à", "às", "ao", "aos", "de", "da", "do", "das",
             "dos", "e", "em", "no", "na", "nos", "nas", "que", "para", "por", "com",
             "um", "uma", "se", "sua", "seu", "é", "ou", "não", "nao"}


def norm(s):
    """Normaliza texto: entidades HTML/XML, acentos, caixa e espaços.

    Desescapa entidades (&quot; etc. — dialetos que devolvem XML escapado,
    ex. bnp-api), remove acentuação, converte para minúsculas e normaliza
    espaços em branco.
    """
    s = html.unescape(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").casefold()
    return re.sub(r"\s+", " ", s).strip()


def fragmentar(trecho, limiar=60):
    """Divide nos cortes internos ("(...)" etc.); mantém só fragmentos com
    >= limiar chars normalizados (mesma régua do gate de citações)."""
    return [f for f in RE_CORTE.split(trecho) if len(norm(f)) >= limiar]


def casar_trecho(trecho, textos_oficiais, limiar=60):
    """(ok, fragmento_reprovado). ok=True quando TODO fragmento relevante do
    trecho aparece (normalizado) em ALGUM dos textos oficiais."""
    corpus = "  ".join(norm(t) for t in textos_oficiais)
    frags = fragmentar(trecho, limiar) or ([trecho] if norm(trecho) else [])
    for frag in frags:
        if norm(frag) not in corpus:
            return False, frag
    return True, None


def frase_de_busca(fragmento, n_palavras=5):
    """Primeiras n palavras de conteúdo (pula stopwords), sem pontuação nas
    bordas — frase CURTA de recuperação, robusta a bases que descartam
    artigos/preposições na indexação (dialeto CJF)."""
    palavras = [re.sub(r"^\W+|\W+$", "", p) for p in fragmento.split()]
    conteudo = [p for p in palavras if p and p.casefold() not in STOPWORDS]
    return " ".join(conteudo[:n_palavras])


def parse_referencia(fonte):
    """Estratégia de identidade a partir da referência + origem/tribunal.
    'precedente' -> nr/tipos para o BNP; 'processo' -> número CNJ;
    'frases' -> recuperação por frases curtas do próprio trecho."""
    ref = (fonte.get("referencia") or "").strip()
    tribunal = (fonte.get("tribunal") or "").strip().upper()
    m = RE_SV.match(ref)
    if m:
        return {"estrategia": "precedente", "nr": m.group(1).replace(".", ""), "tipos": ["SV"]}
    m = RE_TEMA.match(ref)
    if m:
        tipos = ["RR"] if tribunal == "STJ" else ["RG"]
        return {"estrategia": "precedente", "nr": m.group(1).replace(".", ""), "tipos": tipos}
    m = RE_SUM.match(ref)
    if m:
        return {"estrategia": "precedente", "nr": m.group(1).replace(".", ""), "tipos": ["SUM"]}
    m = RE_CC.match(ref)
    if m:
        return {"estrategia": "precedente", "nr": m.group(2).replace(".", ""),
                "tipos": [m.group(1).upper()]}
    m = RE_CNJ.search(ref)
    if m:
        return {"estrategia": "processo", "cnj": m.group(0)}
    return {"estrategia": "frases"}
