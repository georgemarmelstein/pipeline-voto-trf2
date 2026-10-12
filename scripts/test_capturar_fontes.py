#!/usr/bin/env python3
"""test_capturar_fontes.py - Captura nascida-verificada (sem rede).

Roda com: python scripts/test_capturar_fontes.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capturar_fontes as cf

TESE = ("São legítimas as alterações introduzidas pela Medida Provisória 1.858/1999, "
        "no que revogou a isenção da COFINS e da contribuição para o PIS concedidas "
        "às sociedades cooperativas.")
XML_BNP = f"<precedente><tese>{TESE}</tese><situacao>transitado</situacao></precedente>"


def caso(nome, cond):
    print(("[OK] " if cond else "[ERRO] ") + nome)
    return cond


def main():
    ok = True
    sel_tese = {"origem_mcp": "bnp-api", "processo": "0000001-11.2026.4.05.8100",
                "selecoes": [{"referencia": "Tema 177", "tribunal": "STF",
                              "tipo": "repercussao-geral", "campo": "tese"}]}
    fontes, rejeicoes = cf.capturar(sel_tese, obter=lambda f, m=3: [XML_BNP])
    ok &= caso("campo tese: corte determinístico do oficial",
               fontes and fontes[0]["trecho_verbatim"] == TESE and not rejeicoes)

    frag = TESE[:80]
    sel_frag = {"origem_mcp": "julia-trf5", "processo": "0000001-11.2026.4.05.8100",
                "selecoes": [{"referencia": "0000008-88.2022.4.05.8100",
                              "tribunal": "TRF5", "tipo": "acordao",
                              "campo": "acordao", "trecho_proposto": TESE}]}
    fontes, rejeicoes = cf.capturar(sel_frag, obter=lambda f, m=3: ["..." + TESE + "..."])
    ok &= caso("fragmento proposto que casa: aceito", len(fontes) == 1 and not rejeicoes)

    sel_falso = {"origem_mcp": "julia-trf5", "processo": "0000001-11.2026.4.05.8100",
                 "selecoes": [{"referencia": "0000008-88.2022.4.05.8100",
                               "tribunal": "TRF5", "tipo": "acordao", "campo": "acordao",
                               "trecho_proposto": TESE.replace("COFINS", "CSLL")}]}
    fontes, rejeicoes = cf.capturar(sel_falso, obter=lambda f, m=3: ["..." + TESE + "..."])
    ok &= caso("fragmento proposto que NÃO casa: rejeitado no nascimento",
               len(fontes) == 0 and len(rejeicoes) == 1)

    sel_sem = {"origem_mcp": "julia-trf5", "processo": "x",
               "selecoes": [{"referencia": "0000008-88.2022.4.05.8100",
                             "tribunal": "TRF5", "tipo": "acordao", "campo": "acordao"}]}
    fontes, rejeicoes = cf.capturar(sel_sem, obter=lambda f, m=3: [TESE])
    ok &= caso("fragmento sem trecho_proposto: rejeitado", len(rejeicoes) == 1)

    # Finding 1: campo "decisao" normalizado para "sentenca"
    sel_decisao = {"origem_mcp": "julia-trf5", "processo": "0000001-11.2026.4.05.8100",
                   "selecoes": [{"referencia": "0000008-88.2022.4.05.8100",
                                 "tribunal": "TRF5", "tipo": "sentenca",
                                 "campo": "decisao", "trecho_proposto": TESE}]}
    fontes, rejeicoes = cf.capturar(sel_decisao, obter=lambda f, m=3: ["..." + TESE + "..."])
    ok &= caso("campo decisao normalizado para sentenca",
               len(fontes) == 1 and fontes[0]["campo"] == "sentenca" and not rejeicoes)

    # Finding 2a: ementa sem tags XML mas trecho_proposto existe no texto
    ementa_text = "Este é um parecer sobre direitos fundamentais e questões de constitucionalidade"
    sel_ementa_fallback = {"origem_mcp": "bnp-api", "processo": "0000001-11.2026.4.05.8100",
                           "selecoes": [{"referencia": "Tema 100",
                                         "tribunal": "STF", "tipo": "repercussao-geral",
                                         "campo": "ementa",
                                         "trecho_proposto": "direitos fundamentais"}]}
    fontes, rejeicoes = cf.capturar(sel_ementa_fallback, obter=lambda f, m=3: [ementa_text])
    ok &= caso("ementa sem tags XML: fallback trecho_proposto aceito",
               len(fontes) == 1 and fontes[0]["trecho_verbatim"] == "direitos fundamentais" and not rejeicoes)

    # Finding 2b: ementa sem tags XML e trecho_proposto NÃO existe no texto
    sel_ementa_reject = {"origem_mcp": "bnp-api", "processo": "0000001-11.2026.4.05.8100",
                         "selecoes": [{"referencia": "Tema 100",
                                       "tribunal": "STF", "tipo": "repercussao-geral",
                                       "campo": "ementa",
                                       "trecho_proposto": "isenção fiscal"}]}
    fontes, rejeicoes = cf.capturar(sel_ementa_reject, obter=lambda f, m=3: [ementa_text])
    ok &= caso("ementa sem tags XML: trecho_proposto inexistente rejeitado",
               len(fontes) == 0 and len(rejeicoes) == 1 and "recort" in rejeicoes[0])

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
