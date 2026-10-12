#!/usr/bin/env python3
"""test_proveniencia_adapters.py - Smoke de importabilidade dos adaptadores.

SEM REDE: garante que (a) cada server.py importa sem subir o servidor
(guarda __main__), (b) as funções-ferramenta são chamáveis diretamente
(SDK oficial devolve a função original), (c) origem sem adaptador dá KeyError.
Roda com: python scripts/test_proveniencia_adapters.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proveniencia_adapters as pa


def caso(nome, cond):
    print(("[OK] " if cond else "[ERRO] ") + nome)
    return cond


def main():
    ok = True
    # Distribuição TRF2: só o servidor do BNP acompanha o repositório; os demais
    # adaptadores (JULIA, CJF, TNU) seguem registrados, mas seus servidores não vêm.
    for origem in ("bnp-api", "julia-trf5", "cjf-jurisprudencia", "tnu-eproc"):
        ok &= caso(f"adaptador registrado: {origem}", origem in pa.ADAPTADORES)
    mod = pa.carregar_servidor("bnp-api")
    ok &= caso("bnp-api: server.py importa sem rodar", mod is not None)
    ok &= caso("bnp: buscar_precedentes chamável", callable(mod.buscar_precedentes))
    ok &= caso("bnp: BuscaInput existe", hasattr(mod, "BuscaInput"))
    try:
        pa.obter_textos_oficiais({"origem_mcp": "pesquisa-stj", "referencia": "x",
                                  "tribunal": "STJ", "trecho_verbatim": "y"})
        ok &= caso("origem sem adaptador -> KeyError", False)
    except KeyError:
        ok &= caso("origem sem adaptador -> KeyError", True)

    # Teste novo: fonte malformada (sem trecho_verbatim) deve dar KeyError, não BaseIndisponivel
    try:
        pa.obter_textos_oficiais({"origem_mcp": "bnp-api", "referencia": "x",
                                  "tribunal": "STJ"})  # falta trecho_verbatim
        ok &= caso("fonte malformada -> KeyError, não BaseIndisponivel", False)
    except pa.BaseIndisponivel:
        ok &= caso("fonte malformada -> KeyError, não BaseIndisponivel", False)
    except KeyError:
        ok &= caso("fonte malformada -> KeyError, não BaseIndisponivel", True)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
