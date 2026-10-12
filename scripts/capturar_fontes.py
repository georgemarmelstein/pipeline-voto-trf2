#!/usr/bin/env python3
"""capturar_fontes.py - Camada A: fontes nascem VERIFICADAS.

O agente pesquisador escolhe (selecao-<origem>.json); este script busca o texto
oficial pela identidade e:
  - campo tese/sumula: CORTA o campo oficial (<tese>/<sumula>/<ementa>) — zero LLM;
  - campo ementa: corta <ementa>; se ausente, exige trecho_proposto;
  - campo acordao/sentenca: exige trecho_proposto do agente e SÓ grava se
    casar_trecho confirmar contra o texto oficial (rejeição no nascimento).
Normalização: "decisao" é aceito na seleção e normalizado para "sentenca"
(Contrato C1 usa "sentenca" para trecho de sentença/decisão de 1º grau).
Grava fontes-<origem>.json (Contrato C1, aceito pelo merge_fontes.py) e o dossiê
bruto em custodia/ (consulta + resposta + sha256 + data).

Uso:
  python scripts/capturar_fontes.py <workspace> --selecao selecao-bnp.json [--id N]
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proveniencia_core import casar_trecho
from proveniencia_adapters import BaseIndisponivel, obter_textos_oficiais

RE_CNJ = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")
CAMPOS_CORTE = {"tese": r"<tese>(.*?)</tese>",
                "sumula": r"<tese>(.*?)</tese>|<sumula>(.*?)</sumula>",
                "ementa": r"<ementa>(.*?)</ementa>"}


def _cortar_campo(campo, textos):
    padrao = CAMPOS_CORTE[campo]
    for texto in textos:
        m = re.search(padrao, texto, re.DOTALL)
        if m:
            trecho = next(g for g in m.groups() if g)
            return re.sub(r"\s+", " ", trecho).strip()
    return None


def capturar(selecao, obter):
    """(fontes_validas, rejeicoes). Sem I/O de arquivo — o main grava."""
    fontes, rejeicoes = [], []
    origem = selecao["origem_mcp"]
    for sel in selecao.get("selecoes", []):
        campo = sel.get("campo", "")
        # Normalização declarada — o Contrato C1 usa "sentenca" para decisão de 1º grau
        if campo == "decisao":
            campo = "sentenca"
        fonte = {"origem_mcp": origem, "tribunal": sel.get("tribunal", ""),
                 "tipo": sel.get("tipo", ""), "referencia": sel.get("referencia", ""),
                 "orgao_julgador": sel.get("orgao_julgador"),
                 "data_julgamento": sel.get("data_julgamento"),
                 "campo": campo, "url": sel.get("url"),
                 "trecho_verbatim": sel.get("trecho_proposto", "")}
        try:
            textos = obter(fonte)
        except BaseIndisponivel as e:
            rejeicoes.append(f"{fonte['referencia']}: base indisponível ({e})")
            continue
        if fonte["campo"] in CAMPOS_CORTE:
            trecho = _cortar_campo(fonte["campo"], textos)
            if trecho is None and sel.get("trecho_proposto"):
                casou, _ = casar_trecho(sel["trecho_proposto"], textos)
                trecho = sel["trecho_proposto"] if casou else None
            if trecho is None:
                rejeicoes.append(f"{fonte['referencia']}: campo {fonte['campo']} "
                                 "não recortável do texto oficial")
                continue
            fonte["trecho_verbatim"] = trecho
        else:
            proposto = sel.get("trecho_proposto", "")
            if not proposto:
                rejeicoes.append(f"{fonte['referencia']}: campo {fonte['campo']} "
                                 "exige trecho_proposto")
                continue
            casou, frag = casar_trecho(proposto, textos)
            if not casou:
                rejeicoes.append(f"{fonte['referencia']}: trecho proposto sem eco "
                                 f"no oficial ({(frag or proposto)[:60]}...)")
                continue
        fonte["_bruto"] = textos  # o main arquiva e remove antes de gravar
        fontes.append(fonte)
    return fontes, rejeicoes


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Captura nascida-verificada (Camada A).")
    ap.add_argument("workspace")
    ap.add_argument("--selecao", required=True,
                    help="nome do arquivo selecao-<origem>.json dentro do workspace")
    ap.add_argument("--id", dest="ident")
    a = ap.parse_args()

    if not os.path.isdir(a.workspace):
        print(f"[ERRO] workspace inexistente: {a.workspace}")
        sys.exit(2)
    caminho_sel = os.path.join(a.workspace, a.selecao)
    if not os.path.exists(caminho_sel):
        print(f"[ERRO] seleção inexistente: {caminho_sel}")
        sys.exit(2)
    with open(caminho_sel, encoding="utf-8") as f:
        selecao = json.load(f)
    origem = selecao["origem_mcp"]
    sufixo = re.sub(r"^selecao-|\.json$", "", a.selecao)

    print(f"[INICIO] {len(selecao.get('selecoes', []))} seleção(ões) de {origem}")
    fontes, rejeicoes = capturar(selecao, obter=obter_textos_oficiais)

    pasta_custodia = os.path.join(a.workspace, "custodia")
    os.makedirs(pasta_custodia, exist_ok=True)
    for n, fonte in enumerate(fontes, 1):
        bruto = "\n---\n".join(fonte.pop("_bruto"))
        dossie = {"consulta": {"origem_mcp": origem,
                               "referencia": fonte["referencia"]},
                  "resposta_bruta": bruto,
                  "sha256": hashlib.sha256(bruto.encode("utf-8")).hexdigest(),
                  "data": time.strftime("%Y-%m-%d %H:%M")}
        with open(os.path.join(pasta_custodia, f"captura-{sufixo}-{n:02d}.json"),
                  "w", encoding="utf-8") as f:
            json.dump(dossie, f, ensure_ascii=False, indent=2)
        print(f"[OK] {fonte['referencia']}: capturada ({fonte['campo']})")
    for motivo in rejeicoes:
        print(f"[ERRO] rejeitada no nascimento: {motivo}")

    saida = os.path.join(a.workspace, f"fontes-{sufixo}.json")
    with open(saida, "w", encoding="utf-8") as f:
        json.dump({"processo": selecao.get("processo", ""), "versao": 1,
                   "fontes": fontes}, f, ensure_ascii=False, indent=2)
    print(f"[FIM] {len(fontes)} capturadas, {len(rejeicoes)} rejeitadas -> {saida}")
    sys.exit(1 if rejeicoes else 0)


if __name__ == "__main__":
    main()
