#!/usr/bin/env python3
"""test_verificar_proveniencia.py - Testes do gate de proveniência (sem rede).

Unidade: processar_fontes com `obter` fake. Integração: CLI --offline com cache
semeado. Roda com: python scripts/test_verificar_proveniencia.py
"""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import verificar_proveniencia as vp
from proveniencia_core import (CONFIRMADA, NAO_ENCONTRADA, BASE_INDISPONIVEL,
                               SEM_ADAPTADOR)
from proveniencia_adapters import BaseIndisponivel

TESE = ("É legítima a revogação da isenção estabelecida no art. 6º, II, da Lei "
        "Complementar 70/1991 pelo art. 56 da Lei 9.430/1996, dado que a LC 70/1991 "
        "é apenas formalmente complementar, mas materialmente ordinária.")


def fonte(id_, origem="bnp-api", trecho=TESE, referencia="Tema 71"):
    return {"id": id_, "origem_mcp": origem, "tribunal": "STF", "tipo": "rg",
            "referencia": referencia, "campo": "tese", "trecho_verbatim": trecho}


def caso(nome, cond):
    print(("[OK] " if cond else "[ERRO] ") + nome)
    return cond


def main():
    vp.PAUSA_S = 0  # retry não pode dormir 3s nos testes
    ok = True
    gate = os.path.join(AQUI, "verificar_proveniencia.py")
    # 1. texto oficial contém o trecho -> CONFIRMADA
    r = vp.processar_fontes([fonte("BNP-001")], set(),
                            obter=lambda f, m=3: ["EMENTA: " + TESE], cache={})
    ok &= caso("trecho presente -> CONFIRMADA", r[0]["estado"] == CONFIRMADA)
    # 2. trecho adulterado -> NAO_ENCONTRADA
    r = vp.processar_fontes([fonte("BNP-002", trecho=TESE.replace("9.430", "9.999"))],
                            set(), obter=lambda f, m=3: ["EMENTA: " + TESE], cache={})
    ok &= caso("adulterado -> NAO_ENCONTRADA", r[0]["estado"] == NAO_ENCONTRADA)
    # 3. base fora do ar -> BASE_INDISPONIVEL (nunca NAO_ENCONTRADA)
    def caiu(f, m=3):
        raise BaseIndisponivel("timeout")
    r = vp.processar_fontes([fonte("BNP-003")], set(), obter=caiu, cache={})
    ok &= caso("timeout -> BASE_INDISPONIVEL", r[0]["estado"] == BASE_INDISPONIVEL)
    # 4. origem sem adaptador -> SEM_ADAPTADOR
    r = vp.processar_fontes([fonte("STJ-001", origem="pesquisa-stj")], set(),
                            obter=vp.obter_padrao, cache={})
    ok &= caso("pesquisa-stj -> SEM_ADAPTADOR", r[0]["estado"] == SEM_ADAPTADOR)
    # 5. cache: segunda passada não chama a rede
    chamadas = []
    def contando(f, m=3):
        chamadas.append(f["id"])
        return ["EMENTA: " + TESE]
    cache = {}
    vp.processar_fontes([fonte("BNP-004")], set(), obter=contando, cache=cache)
    vp.processar_fontes([fonte("BNP-004")], set(), obter=contando, cache=cache)
    ok &= caso("cache evita segunda consulta", chamadas == ["BNP-004"])

    # 6. CLI --offline: cache semeado com CONFIRMADA -> exit 0; sem cache -> exit 1
    with tempfile.TemporaryDirectory() as d:
        numero = "0000001-11.2026.4.05.8100"
        ws = os.path.join(d, numero)
        os.makedirs(os.path.join(ws, "custodia"))
        fontes_doc = {"processo": numero, "versao": 1, "fontes": [fonte("BNP-001")]}
        with open(os.path.join(ws, numero + "-fontes.json"), "w", encoding="utf-8") as f:
            json.dump(fontes_doc, f, ensure_ascii=False)
        with open(os.path.join(ws, numero + "-citaveis.json"), "w", encoding="utf-8") as f:
            json.dump({"processo": numero, "fontes": [{"referencia": "Tema 71",
                       "motivo": "precedente qualificado sobre o objeto",
                       "referencias_equivalentes": ["Tema 71", "RE 377.457"]}],
                       "praxe": []}, f, ensure_ascii=False)
        chave = vp.chave_fonte(fonte("BNP-001"))
        with open(os.path.join(ws, "custodia", "proveniencia-cache.json"),
                  "w", encoding="utf-8") as f:
            json.dump({chave: {"estado": CONFIRMADA, "data": "2026-07-24",
                               "detalhe": ""}}, f)
        r = subprocess.run([sys.executable, gate, ws, "--offline"],
                           capture_output=True, text=True)
        ok &= caso("CLI offline com cache CONFIRMADA -> exit 0", r.returncode == 0)
        os.remove(os.path.join(ws, "custodia", "proveniencia-cache.json"))
        r = subprocess.run([sys.executable, gate, ws, "--offline"],
                           capture_output=True, text=True)
        ok &= caso("CLI offline sem cache: citável indisponível -> exit 1",
                   r.returncode == 1)

    # 7. fonte malformada (sem trecho_verbatim) NAO pode virar SEM_ADAPTADOR
    #    silencioso — é bug do chamador, deve estourar alto (KeyError)
    fonte_sem_trecho = {"id": "BNP-005", "origem_mcp": "bnp-api", "tribunal": "STF",
                        "tipo": "rg", "referencia": "Tema 71", "campo": "tese"}
    levantou_keyerror = False
    try:
        vp.processar_fontes([fonte_sem_trecho], set(),
                            obter=lambda f, m=3: ["texto qualquer"], cache={})
    except KeyError:
        levantou_keyerror = True
    ok &= caso("fonte sem trecho_verbatim -> KeyError explícito (bug do "
               "chamador, não SEM_ADAPTADOR)", levantou_keyerror)

    # 8/9. citaveis.json ausente NUNCA é silencioso; --exigir-citaveis bloqueia
    with tempfile.TemporaryDirectory() as d:
        numero = "0000002-22.2026.4.05.8100"
        ws = os.path.join(d, numero)
        os.makedirs(os.path.join(ws, "custodia"))
        fontes_doc = {"processo": numero, "versao": 1, "fontes": [fonte("BNP-001")]}
        with open(os.path.join(ws, numero + "-fontes.json"), "w", encoding="utf-8") as f:
            json.dump(fontes_doc, f, ensure_ascii=False)
        chave = vp.chave_fonte(fonte("BNP-001"))
        with open(os.path.join(ws, "custodia", "proveniencia-cache.json"),
                  "w", encoding="utf-8") as f:
            json.dump({chave: {"estado": CONFIRMADA, "data": "2026-07-24",
                               "detalhe": ""}}, f)
        r = subprocess.run([sys.executable, gate, ws, "--offline"],
                           capture_output=True, text=True)
        ok &= caso("sem citaveis.json (cedo no pipeline) -> exit 0", r.returncode == 0)
        ok &= caso("sem citaveis.json -> AVISO nunca silencioso",
                   "[AVISO] sem" in r.stdout)
        r2 = subprocess.run([sys.executable, gate, ws, "--offline", "--exigir-citaveis"],
                            capture_output=True, text=True)
        ok &= caso("--exigir-citaveis sem citaveis.json -> exit 1", r2.returncode == 1)
        ok &= caso("--exigir-citaveis -> ERRO explícito",
                   "[ERRO] citaveis.json ausente" in r2.stdout)

    # 10. workspace inexistente -> exit 2
    with tempfile.TemporaryDirectory() as d:
        inexistente = os.path.join(d, "nao-existe")
        r = subprocess.run([sys.executable, gate, inexistente, "--offline"],
                           capture_output=True, text=True)
        ok &= caso("workspace inexistente -> exit 2", r.returncode == 2)

    # 11. fontes.json inexistente em workspace existente -> exit 2
    with tempfile.TemporaryDirectory() as d:
        numero = "0000003-33.2026.4.05.8100"
        ws = os.path.join(d, numero)
        os.makedirs(ws)
        r = subprocess.run([sys.executable, gate, ws, "--offline"],
                           capture_output=True, text=True)
        ok &= caso("fontes.json inexistente -> exit 2", r.returncode == 2)

    # 12. --so-citaveis: só a fonte marcada citável aparece no relatório
    with tempfile.TemporaryDirectory() as d:
        numero = "0000004-44.2026.4.05.8100"
        ws = os.path.join(d, numero)
        os.makedirs(os.path.join(ws, "custodia"))
        f1 = fonte("BNP-010")
        f2 = fonte("BNP-011", referencia="Tema 72")
        fontes_doc = {"processo": numero, "versao": 1, "fontes": [f1, f2]}
        with open(os.path.join(ws, numero + "-fontes.json"), "w", encoding="utf-8") as fh:
            json.dump(fontes_doc, fh, ensure_ascii=False)
        with open(os.path.join(ws, numero + "-citaveis.json"), "w", encoding="utf-8") as fh:
            json.dump({"processo": numero, "fontes": [{"referencia": "Tema 71",
                       "motivo": "precedente qualificado sobre o objeto",
                       "referencias_equivalentes": []}], "praxe": []},
                      fh, ensure_ascii=False)
        cache = {vp.chave_fonte(f1): {"estado": CONFIRMADA, "data": "2026-07-24", "detalhe": ""},
                 vp.chave_fonte(f2): {"estado": CONFIRMADA, "data": "2026-07-24", "detalhe": ""}}
        with open(os.path.join(ws, "custodia", "proveniencia-cache.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
        r = subprocess.run([sys.executable, gate, ws, "--offline", "--so-citaveis"],
                           capture_output=True, text=True)
        ok &= caso("--so-citaveis: menciona a fonte citável", "BNP-010" in r.stdout)
        ok &= caso("--so-citaveis: NÃO menciona a fonte não citável",
                   "BNP-011" not in r.stdout)

    # 13. citaveis_nao_resolvidos (unidade): match direto, match via
    #     equivalente, e não resolvido (nenhum resultado CONFIRMADA bate)
    resultados_unit = [{"referencia": "Tema 71", "estado": CONFIRMADA},
                       {"referencia": "RE 949.297", "estado": CONFIRMADA},
                       {"referencia": "Tema 55", "estado": BASE_INDISPONIVEL}]
    entradas_unit = [
        {"referencia": "Tema 71"},  # resolvido: match direto
        {"referencia": "Tema 971", "referencias_equivalentes": ["RE 949.297"]},  # resolvido via equivalente
        {"referencia": "Tema 810"},  # NÃO resolvido: nenhum resultado bate
        {"referencia": "Tema 55"},  # NÃO resolvido: bate mas não é CONFIRMADA
    ]
    faltando = vp.citaveis_nao_resolvidos(entradas_unit, resultados_unit)
    ok &= caso("citaveis_nao_resolvidos: resolvidos ficam de fora",
               "Tema 71" not in faltando and "Tema 971" not in faltando)
    ok &= caso("citaveis_nao_resolvidos: sem match nenhum -> na lista",
               "Tema 810" in faltando)
    ok &= caso("citaveis_nao_resolvidos: match sem CONFIRMADA -> na lista",
               "Tema 55" in faltando)

    # 14/15. --exigir-citaveis no gate final: citável sem fonte CONFIRMADA
    #        correspondente BLOQUEIA (exit 1); citável resolvido -> exit 0
    with tempfile.TemporaryDirectory() as d:
        numero = "0000005-55.2026.4.05.8100"
        ws = os.path.join(d, numero)
        os.makedirs(os.path.join(ws, "custodia"))
        f1 = fonte("BNP-020", referencia="Tema 71")
        fontes_doc = {"processo": numero, "versao": 1, "fontes": [f1]}
        with open(os.path.join(ws, numero + "-fontes.json"), "w", encoding="utf-8") as fh:
            json.dump(fontes_doc, fh, ensure_ascii=False)
        cache = {vp.chave_fonte(f1): {"estado": CONFIRMADA, "data": "2026-07-24", "detalhe": ""}}
        with open(os.path.join(ws, "custodia", "proveniencia-cache.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(cache, fh)

        # 14. citável "Tema 810" não corresponde a NENHUMA fonte -> bloqueia
        with open(os.path.join(ws, numero + "-citaveis.json"), "w", encoding="utf-8") as fh:
            json.dump({"processo": numero, "fontes": [{"referencia": "Tema 810",
                       "motivo": "precedente citado na minuta",
                       "referencias_equivalentes": []}], "praxe": []},
                      fh, ensure_ascii=False)
        r14 = subprocess.run([sys.executable, gate, ws, "--offline", "--exigir-citaveis"],
                             capture_output=True, text=True, encoding="utf-8")
        ok &= caso("--exigir-citaveis: citável sem fonte CONFIRMADA -> exit 1",
                   r14.returncode == 1)
        ok &= caso("--exigir-citaveis: mensagem de erro com a referência",
                   "citável sem fonte CONFIRMADA: Tema 810" in r14.stdout)

        # 15. citável "Tema 71" corresponde à fonte CONFIRMADA -> exit 0
        with open(os.path.join(ws, numero + "-citaveis.json"), "w", encoding="utf-8") as fh:
            json.dump({"processo": numero, "fontes": [{"referencia": "Tema 71",
                       "motivo": "precedente citado na minuta",
                       "referencias_equivalentes": []}], "praxe": []},
                      fh, ensure_ascii=False)
        r15 = subprocess.run([sys.executable, gate, ws, "--offline", "--exigir-citaveis"],
                             capture_output=True, text=True, encoding="utf-8")
        ok &= caso("--exigir-citaveis: citável resolvido em CONFIRMADA -> exit 0",
                   r15.returncode == 0)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
