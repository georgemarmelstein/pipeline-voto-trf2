#!/usr/bin/env python3
"""gerar_prancha.py - Camada C: prancha de conferência humana das fontes.

Consolida, POR CITÁVEL: referência, verbatim oficial (a âncora), estado de
proveniência (com data da verificação), veredito de paráfrase e a consulta
reproduzível. O magistrado confere 2–5 itens antes de assinar — este arquivo
é a materialização do princípio "a máquina mostra o trabalho, o humano decide".

Uso:
  python scripts/gerar_prancha.py <workspace> [--id N]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verificar_proveniencia import chave_fonte
from proveniencia_core import norm

RE_CNJ = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")


def _carregar(caminho, default):
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return default


def _veredito(texto_vereditos, referencia):
    """Vereditos são keyed por REFERENCIA (não id — o merge_fontes.py reatribui
    ids a cada rodada). Boundary por `\\s` após a referência escapada evita que
    "Tema 7" case com o cabeçalho de "Tema 71"."""
    m = re.search(rf"(?ms)^## {re.escape(referencia)}\s.*?^VEREDITO:\s*(\S+)",
                  texto_vereditos)
    return m.group(1) if m else "—"


def _refs_normalizadas(entrada):
    """Conjunto de referências normalizadas de um citável: a própria referência
    mais as referencias_equivalentes — a chave de casamento com fontes.json."""
    refs = set()
    ref = entrada.get("referencia", "")
    if ref:
        refs.add(norm(ref))
    for eq in entrada.get("referencias_equivalentes", []) or []:
        if eq:
            refs.add(norm(eq))
    return refs


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Prancha de conferência (Camada C).")
    ap.add_argument("workspace")
    ap.add_argument("--id", dest="ident")
    a = ap.parse_args()
    if not os.path.isdir(a.workspace):
        print(f"[ERRO] workspace inexistente: {a.workspace}")
        sys.exit(2)
    base = os.path.basename(os.path.abspath(a.workspace))
    m = RE_CNJ.search(base)
    ident = a.ident or (m.group(0) if m else base)

    fontes_path = os.path.join(a.workspace, ident + "-fontes.json")
    if not os.path.exists(fontes_path):
        print(f"[ERRO] fontes inexistente: {fontes_path}")
        sys.exit(2)

    citaveis_path = os.path.join(a.workspace, ident + "-citaveis.json")
    if not os.path.exists(citaveis_path):
        print(f"[ERRO] citaveis inexistente: {citaveis_path}")
        sys.exit(2)

    fontes = _carregar(fontes_path, {"fontes": []})["fontes"]
    citaveis = _carregar(citaveis_path, {"fontes": [], "praxe": []})
    cache = _carregar(os.path.join(a.workspace, "custodia",
                                   "proveniencia-cache.json"), {})
    caminho_ver = os.path.join(a.workspace, ident + "-vereditos-parafrase.md")
    vereditos = open(caminho_ver, encoding="utf-8").read() \
        if os.path.exists(caminho_ver) else ""

    entradas_citaveis = citaveis.get("fontes", [])

    linhas = [f"# Prancha de Conferência de Fontes — {ident}", "",
              "Confira cada citável: a paráfrase da minuta deve caber na âncora.", ""]
    fontes_citadas_ids = set()
    for entrada in entradas_citaveis:
        referencia = entrada.get("referencia", "")
        motivo = entrada.get("motivo", "")
        refs_norm = _refs_normalizadas(entrada)
        correspondentes = [f for f in fontes
                           if norm(f.get("referencia", "")) in refs_norm]
        if not correspondentes:
            rotulo = referencia or entrada.get("id", "?")
            linhas += [f"## {rotulo} — AUSENTE DO FONTES.JSON", ""]
            continue
        for fonte in correspondentes:
            fontes_citadas_ids.add(fonte["id"])
            prov = cache.get(chave_fonte(fonte), {})
            linhas += [
                f"## {fonte['id']} — {fonte['referencia']} ({fonte.get('tribunal', '')})",
                f"- **Motivo de citabilidade:** {motivo}",
                f"- **Proveniência:** {prov.get('estado', 'NAO VERIFICADA')}"
                + (f" em {prov['data']}" if prov.get("data") else ""),
                f"- **Veredito de paráfrase:** {_veredito(vereditos, referencia)}",
                f"- **Consulta reproduzível:** {fonte['origem_mcp']} → "
                f"{fonte['referencia']}" + (f" ({fonte['url']})" if fonte.get("url") else ""),
                "", "> " + fonte["trecho_verbatim"].replace("\n", "\n> "), ""]
    if citaveis.get("praxe"):
        linhas += ["## Referências de praxe (sem lastro obrigatório)",
                   ", ".join(citaveis["praxe"]), ""]
    outras = [f for f in fontes if f["id"] not in fontes_citadas_ids]
    if outras:
        linhas += ["## Fontes de análise (não citáveis na minuta)"]
        for f in outras:
            prov = cache.get(chave_fonte(f), {})
            linhas.append(f"- {f['id']} {f['referencia']}: "
                          f"{prov.get('estado', 'NAO VERIFICADA')}")
        linhas.append("")

    saida = os.path.join(a.workspace, ident + "-conferencia-fontes.md")
    with open(saida, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print(f"[FIM] prancha com {len(entradas_citaveis)} citável(is) -> {saida}")
    sys.exit(0)


if __name__ == "__main__":
    main()
