#!/usr/bin/env python3
"""merge_voto.py - Etapa 7 do /pipeline-voto, determinística (v3.0).

Monta o acórdão sem LLM e sem passar conteúdo pelo contexto do orquestrador:

    EMENTA (sem o sinalizador técnico [FIM_EMENTA]) + RELATÓRIO + VOTO
        -> $ID-acordao.md

As três entradas precisam passar no gate (verificar_voto.py); se alguma falhar,
o defeito é da etapa de origem, apontada na linha [ERRO]. O resultado é validado
com as mesmas âncoras normalizadas do gate.

Idempotente: as mesmas entradas produzem sempre o mesmo arquivo. Re-rodar depois
de regenerar voto, ementa ou relatório é a operação normal da Etapa 8 (o gate
acusa o acórdão como desatualizado quando uma entrada fica mais nova que ele).

Uso: python scripts/merge_voto.py <workspace> [--id N]
Exit 0 = acórdão gravado e válido; 1 = entrada ausente/inválida ou resultado
inválido; 2 = erro de uso.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verificar_voto import ETAPAS, avaliar, inferir_id  # noqa: E402

ENTRADAS = ("ementa", "relatorio", "voto")
RE_FIM_EMENTA = re.compile(r"[ \t]*\[FIM_EMENTA\][ \t]*", re.IGNORECASE)


def limpar_ementa(texto):
    """Remove a linha do sinalizador [FIM_EMENTA] (e um resto colado ao fim de linha)."""
    linhas = [ln for ln in texto.splitlines() if ln.strip().upper() != "[FIM_EMENTA]"]
    return RE_FIM_EMENTA.sub("", "\n".join(linhas)).strip()


def montar(ementa, relatorio, voto):
    return (limpar_ementa(ementa) + "\n\n" + relatorio.strip() + "\n\n"
            + voto.strip() + "\n")


def _ler(workspace, ident, etapa):
    with open(os.path.join(workspace, f"{ident}{ETAPAS[etapa][0]}"), encoding="utf-8") as f:
        return f.read()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Merge determinístico ementa+relatório+voto -> acórdão.")
    ap.add_argument("workspace")
    ap.add_argument("--id", "--numero", dest="ident")
    a = ap.parse_args()

    if not os.path.isdir(a.workspace):
        print(f"[ERRO] workspace inexistente: {a.workspace}")
        sys.exit(2)
    ident = a.ident or inferir_id(a.workspace)

    for etapa in ENTRADAS:
        status, info = avaliar(a.workspace, ident, etapa)
        if status != "ok":
            motivo = "ausente" if status == "ausente" else "inválida: " + "; ".join(info or [])
            print(f"[ERRO] entrada {etapa} {motivo}")
            sys.exit(1)

    conteudo = montar(*(_ler(a.workspace, ident, e) for e in ENTRADAS))
    saida = os.path.join(a.workspace, f"{ident}{ETAPAS['acordao'][0]}")
    temporario = saida + ".tmp"
    with open(temporario, "w", encoding="utf-8", newline="\n") as f:
        f.write(conteudo)
    os.replace(temporario, saida)

    status, info = avaliar(a.workspace, ident, "acordao")
    if status != "ok":
        print("[ERRO] acórdão gravado mas inválido: " + "; ".join(info or [status]))
        sys.exit(1)
    print(f"[OK] acordao -> {saida.replace(os.sep, '/')} ({os.path.getsize(saida)} bytes)")
    sys.exit(0)


if __name__ == "__main__":
    main()
