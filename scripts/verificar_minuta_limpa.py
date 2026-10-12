#!/usr/bin/env python3
"""verificar_minuta_limpa.py - Gate v2 da minuta (regime de redação limpa, spec 24/07).

Do heading de abertura da fundamentação (inclusive) até o fim. O marcador aceita
alternativas separadas por vírgula (default "FUNDAMENTACAO,FUNDAMENTO"): a sentença
abre com FUNDAMENTAÇÃO, a decisão interlocutória de saneamento abre com FUNDAMENTO.
Alternativa só casa como título exato em linha própria; o prefixo vale apenas para o
primeiro marcador, para não recortar em prosa que comece pela palavra.
  1. ASPAS: trecho entre aspas com >= max-palavras (default 6) é violação dura;
     aspas curtas são permitidas e listadas como aviso (expressões, nomes de
     documentos). O RELATÓRIO fica fora do gate — relato de parte é livre.
  2. REFERÊNCIAS: toda menção jurisprudencial (Tema, Súmula, SV, ADI/ADC/ADPF,
     RE/REsp/EREsp/AREsp, número CNJ) deve estar na lista de citáveis
     ($NUMERO-citaveis.json: referencias_equivalentes) ou na lista `praxe`.
     Legislação (art., Lei, LC) é livre — referenciada sem transcrição.
  3. VEREDITOS: se $NUMERO-vereditos-parafrase.md existe, REFUTADAS deve ser 0;
     com --exigir-vereditos a ausência do arquivo também reprova (gate final).
  4. PUBLICAÇÃO: a minuta é colada no editor do PJE, que não interpreta markdown.
     O DOCUMENTO INTEIRO (relatório incluído) reprova com markdown decorativo
     (títulos #, negrito, itálico, listas, tabelas, blocos) ou sinalizador
     interno do pipeline vazado (ESCALAR:/MOTIVO:, [VERIFICAR, [LACUNA).

Limitação declarada (v1): enumerações "Súmulas 512 e 105" capturam só o primeiro
número; a prancha de conferência cobre o resíduo.

Uso:
  python scripts/verificar_minuta_limpa.py <workspace> [--id N] [--doc=-sentenca.md]
      [--a-partir-de FUNDAMENTACAO] [--max-palavras 6] [--exigir-vereditos]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proveniencia_core import RE_CORTE, norm, RE_CNJ

RE_ASPAS = re.compile('"([^"]+)"|' + '“([^”]+)”', re.DOTALL)
# Contaminação de publicação (mesma família do verificar_embargos.py, mais o
# itálico de um asterisco, que exige conteúdo colado aos delimitadores para não
# capturar asteriscos soltos em prosa).
PROIBIDOS_PUBLICACAO = [
    (re.compile(r"^\s*#{1,6} ", re.MULTILINE), "título markdown (#)"),
    (re.compile(r"\*\*"), "negrito markdown (**)"),
    (re.compile(r"(?<!\*)\*(?!\s)[^*\n]*[^*\s]\*(?!\*)"), "itálico markdown (*)"),
    (re.compile(r"```"), "bloco de código markdown"),
    (re.compile(r"^\s*> ", re.MULTILINE), "citação em bloco markdown (>)"),
    (re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE), "tabela markdown"),
    (re.compile(r"^\s*[-*+] ", re.MULTILINE), "lista markdown (-/*/+)"),
    (re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE),
     "régua horizontal markdown (---)"),
    (re.compile(r"^(ESCALAR|MOTIVO):", re.MULTILINE),
     "sinalizador interno ESCALAR:/MOTIVO: vazado da análise"),
    (re.compile(r"\[VERIFICAR"), "sinalizador [VERIFICAR] no corpo"),
    (re.compile(r"\[LACUNA"), "sinalizador [LACUNA] no corpo"),
]
RE_REFS = [
    ("TEMA", re.compile(r"(?i)\btemas?(?:\s+repetitivos?)?\s+n?[ºo°.]?\s*(\d+)")),
    ("SV", re.compile(r"(?i)\bs[úu]mulas?\s+vinculantes?\s+n?[ºo°.]?\s*(\d+)")),
    ("SV", re.compile(r"(?i)\bSV\s+(\d+)")),
    ("SUM", re.compile(r"(?i)\bs[úu]mulas?\s+(?!vinculante)n?[ºo°.]?\s*(\d+)")),
    ("CC", re.compile(r"(?i)\b(ADI|ADC|ADPF|ADO)\s+n?[ºo°.]?\s*([\d.]+)")),
    ("REC", re.compile(r"(?i)\b(RE|AREsp|EREsp|REsp)\s+n?[ºo°.]?\s*([\d.]+)")),
    ("CNJ", RE_CNJ),
]


def token_ref(tipo, numero):
    return tipo + re.sub(r"\D", "", numero)


def tokens_de_texto(texto):
    achados = []
    for tipo, rx in RE_REFS:
        for m in rx.finditer(texto):
            if tipo in ("CC", "REC"):
                achados.append((token_ref(m.group(1).upper(), m.group(2)), m.group(0)))
            elif tipo == "CNJ":
                achados.append((token_ref("CNJ", m.group(0)), m.group(0)))
            else:
                achados.append((token_ref(tipo, m.group(1)), m.group(0)))
    return achados


def tokens_permitidos(citaveis):
    permitidos = set()
    for entrada in citaveis.get("fontes", []):
        for ref in entrada.get("referencias_equivalentes", []):
            permitidos.update(t for t, _ in tokens_de_texto(ref))
    for ref in citaveis.get("praxe", []):
        permitidos.update(t for t, _ in tokens_de_texto(ref))
    return permitidos


def recortar_a_partir(texto, marcador):
    # Aceita alternativas separadas por vírgula: a sentença abre a seção com
    # FUNDAMENTAÇÃO, a decisão interlocutória de saneamento abre com FUNDAMENTO.
    alvos = [norm(m) for m in marcador.split(",") if norm(m)]
    linhas = texto.splitlines(keepends=True)
    conteudos = [norm(re.sub(r"^#+\s*", "", linha)) for linha in linhas]
    # 1ª passada: título exato em linha própria (vale para qualquer alternativa).
    for i, conteudo in enumerate(conteudos):
        if conteudo in alvos:
            return "".join(linhas[i:]), i + 1
    # 2ª passada: prefixo, apenas do marcador principal (compatibilidade).
    for i, conteudo in enumerate(conteudos):
        if alvos and conteudo.startswith(alvos[0]):
            return "".join(linhas[i:]), i + 1
    return texto, None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Gate da minuta limpa (v3.2).")
    ap.add_argument("workspace")
    ap.add_argument("--id", dest="ident")
    ap.add_argument("--doc", default="-sentenca.md")
    ap.add_argument("--a-partir-de", dest="marcador",
                    default="FUNDAMENTACAO,FUNDAMENTO")
    ap.add_argument("--max-palavras", type=int, default=6)
    ap.add_argument("--exigir-vereditos", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(a.workspace):
        print(f"[ERRO] workspace inexistente: {a.workspace}")
        sys.exit(2)
    base = os.path.basename(os.path.abspath(a.workspace))
    m = RE_CNJ.search(base)
    ident = a.ident or (m.group(0) if m else base)
    doc = a.doc if os.path.sep in a.doc or os.path.exists(a.doc) \
        else os.path.join(a.workspace, ident + a.doc)
    if not os.path.exists(doc):
        print(f"[ERRO] documento inexistente: {doc}")
        sys.exit(2)

    caminho_cit = os.path.join(a.workspace, ident + "-citaveis.json")
    citaveis = {"fontes": [], "praxe": []}
    avisos = []
    if os.path.exists(caminho_cit):
        try:
            with open(caminho_cit, encoding="utf-8") as f:
                citaveis = json.load(f)
        except json.JSONDecodeError:
            print("[ERRO] citaveis.json inválido (JSON malformado)")
            sys.exit(2)
    else:
        avisos.append("sem citaveis.json — toda referência jurisprudencial reprova")
    permitidos = tokens_permitidos(citaveis)

    texto = open(doc, encoding="utf-8").read()
    corpo, linha = recortar_a_partir(texto, a.marcador)
    if linha is None:
        avisos.append(f"marcador {a.marcador!r} não achado — documento inteiro no gate")
    problemas = []

    # 0. publicação — documento INTEIRO (o relatório também é colado no PJE)
    for rx, motivo in PROIBIDOS_PUBLICACAO:
        if rx.search(texto):
            problemas.append(f"contaminação de publicação: {motivo}")

    # 1. aspas
    conferidas = 0
    for m2 in RE_ASPAS.finditer(corpo):
        bruto = m2.group(1) or m2.group(2)
        conferidas += 1
        for frag in RE_CORTE.split(bruto):
            if len(frag.split()) >= a.max_palavras:
                problemas.append("aspas longas na minuta: \""
                                 + re.sub(r"\s+", " ", frag).strip()[:80] + "...\"")
                break
        else:
            avisos.append(f"aspas curtas permitidas: \"{bruto.strip()[:50]}\"")

    # 2. referências
    reportados = set()
    for token, literal in tokens_de_texto(corpo):
        if token not in permitidos and token not in reportados:
            problemas.append(f"referência fora dos citáveis: {literal} ({token})")
            reportados.add(token)

    # 3. vereditos de paráfrase
    caminho_ver = os.path.join(a.workspace, ident + "-vereditos-parafrase.md")
    if os.path.exists(caminho_ver):
        conteudo = open(caminho_ver, encoding="utf-8").read()
        m3 = re.search(r"(?im)^REFUTADAS:\s*(\d+)", conteudo)
        if not m3:
            problemas.append("vereditos-parafrase sem linha 'REFUTADAS: N'")
        elif int(m3.group(1)) > 0:
            problemas.append(f"paráfrase(s) refutada(s): {m3.group(1)}")
    elif a.exigir_vereditos:
        problemas.append("vereditos-parafrase ausente (--exigir-vereditos)")

    print(f"[INICIO] {os.path.basename(doc)} -> minuta limpa "
          f"({conferidas} aspas examinadas)")
    for av in avisos:
        print(f"[AVISO] {av}")
    for p in problemas:
        print(f"[ERRO] {p}")
    print(f"[FIM] {len(problemas)} violação(ões)")
    sys.exit(1 if problemas else 0)


if __name__ == "__main__":
    main()
