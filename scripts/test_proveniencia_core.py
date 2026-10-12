#!/usr/bin/env python3
"""test_proveniencia_core.py - Testes do núcleo puro de proveniência.

Roda com: python scripts/test_proveniencia_core.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proveniencia_core as pc


def caso(nome, cond):
    print(("[OK] " if cond else "[ERRO] ") + nome)
    return cond


def main():
    ok = True
    # norm: acentos, caixa e espaços
    ok &= caso("norm normaliza acento/caixa/espacos",
               pc.norm("  Revogação   da ISENÇÃO ") == "revogacao da isencao")

    # fragmentar: corte interno divide; fragmentos curtos caem fora
    trecho = ("A iminente cobrança de tributo autoriza o uso de mandado de segurança "
              "preventivo, estando descaracterizada a impetração contra a lei em tese. "
              "(...) A pessoa jurídica que opte pelo SIMPLES está obrigada a pagar a "
              "contribuição para a seguridade social de seus empregados.")
    frags = pc.fragmentar(trecho)
    ok &= caso("fragmentar divide no corte interno", len(frags) == 2)
    ok &= caso("fragmentar descarta curtos", pc.fragmentar("ok. (...) sim.") == [])

    # casar_trecho: casa quando todos os fragmentos estão em algum texto oficial
    oficial = "EMENTA COMPLETA: " + trecho.replace("(...)", " ")
    ok &= caso("casar_trecho confirma", pc.casar_trecho(trecho, [oficial])[0] is True)
    adulterado = trecho.replace("SIMPLES", "SIMPÁTICO")
    casou, frag = pc.casar_trecho(adulterado, [oficial])
    ok &= caso("casar_trecho pega adulteração de 1 palavra", casou is False and frag is not None)

    # frase_de_busca: primeiras palavras de conteúdo, sem stopwords iniciais
    ok &= caso("frase_de_busca pula stopwords",
               pc.frase_de_busca("A iminente cobrança de tributo autoriza o uso")
               == "iminente cobrança tributo autoriza uso")

    # parse_referencia: precedentes BNP
    f = {"origem_mcp": "bnp-api", "tribunal": "STF", "referencia": "Tema 71"}
    r = pc.parse_referencia(f)
    ok &= caso("Tema STF -> RG", r == {"estrategia": "precedente", "nr": "71", "tipos": ["RG"]})
    f = {"origem_mcp": "bnp-api", "tribunal": "STJ", "referencia": "Tema 1273"}
    ok &= caso("Tema STJ -> RR", pc.parse_referencia(f)["tipos"] == ["RR"])
    f = {"origem_mcp": "bnp-api", "tribunal": "STF", "referencia": "SV 62"}
    ok &= caso("SV", pc.parse_referencia(f)["tipos"] == ["SV"])
    f = {"origem_mcp": "bnp-api", "tribunal": "STF", "referencia": "Súmula 266"}
    ok &= caso("Súmula comum", pc.parse_referencia(f)["tipos"] == ["SUM"])
    # processo CNJ (com ou sem prefixo de classe)
    f = {"origem_mcp": "julia-trf5", "tribunal": "TRF5",
         "referencia": "ApCiv 0000007-77.2026.4.05.8100"}
    r = pc.parse_referencia(f)
    ok &= caso("CNJ com classe", r == {"estrategia": "processo",
                                        "cnj": "0000007-77.2026.4.05.8100"})
    # sem identidade estruturada -> frases
    f = {"origem_mcp": "cjf-jurisprudencia", "tribunal": "TRF4",
         "referencia": "AG 1999.04.01.035314-4"}
    ok &= caso("número antigo -> frases", pc.parse_referencia(f)["estrategia"] == "frases")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
