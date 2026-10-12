#!/usr/bin/env python3
"""test_gerar_prancha.py - Prancha de conferência humana.

Roda com: python scripts/test_gerar_prancha.py
"""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from verificar_proveniencia import chave_fonte
from gerar_prancha import _veredito

NUMERO = "0000001-11.2026.4.05.8100"
FONTE = {"id": "BNP-001", "origem_mcp": "bnp-api", "tribunal": "STF",
         "tipo": "repercussao-geral", "referencia": "Tema 71",
         "orgao_julgador": None, "data_julgamento": None, "campo": "tese",
         "trecho_verbatim": "É legítima a revogação da isenção estabelecida no "
                            "art. 6º, II, da Lei Complementar 70/1991.", "url": None}


def caso(nome, cond):
    print(("[OK] " if cond else "[ERRO] ") + nome)
    return cond


def test_veredito_prefix_boundary():
    """RED: veredito deve diferenciar "Tema 7" de "Tema 71" (chave = referencia)."""
    ok = True
    texto = """# Vereditos de Paráfrase

## Tema 71
VEREDITO: REFUTADA

## Tema 7
VEREDITO: FIEL
"""
    ok &= caso("_veredito Tema 7 retorna FIEL", _veredito(texto, "Tema 7") == "FIEL")
    ok &= caso("_veredito Tema 71 retorna REFUTADA", _veredito(texto, "Tema 71") == "REFUTADA")

    # "Tema 7" só existe como prefixo de "Tema 71": deve retornar "—"
    texto2 = """# Vereditos de Paráfrase

## Tema 71
VEREDITO: REFUTADA
"""
    ok &= caso("_veredito Tema 7 não encontrada retorna —", _veredito(texto2, "Tema 7") == "—")
    return ok


def test_multiline_verbatim():
    """RED: blockquote multiline deve prefixar toda linha."""
    ok = True
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, NUMERO)
        os.makedirs(os.path.join(ws, "custodia"))

        fonte_ml = FONTE.copy()
        fonte_ml["trecho_verbatim"] = "Primeira linha.\nSegunda linha.\nTerceira linha."

        json.dump({"processo": NUMERO, "versao": 1, "fontes": [fonte_ml]},
                  open(os.path.join(ws, NUMERO + "-fontes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({"processo": NUMERO,
                   "fontes": [{"id": "BNP-001", "referencia": "Tema 71",
                               "motivo": "objeto do caso"}],
                   "praxe": []},
                  open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({}, open(os.path.join(ws, "custodia", "proveniencia-cache.json"), "w"))

        r = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_prancha.py"), ws],
                          capture_output=True, text=True)
        texto = open(os.path.join(ws, NUMERO + "-conferencia-fontes.md"), encoding="utf-8").read()
        ok &= caso("multiline: linha 1 prefixada", "> Primeira linha." in texto)
        ok &= caso("multiline: linha 2 prefixada", "> Segunda linha." in texto)
        ok &= caso("multiline: linha 3 prefixada", "> Terceira linha." in texto)
    return ok


def test_missing_fontes_json():
    """RED: sem fontes.json → exit 2."""
    ok = True
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, NUMERO)
        os.makedirs(os.path.join(ws, "custodia"))
        # Não cria fontes.json
        json.dump({"processo": NUMERO, "fontes": [], "praxe": []},
                  open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)

        r = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_prancha.py"), ws],
                          capture_output=True, text=True)
        ok &= caso("sem fontes.json: exit 2", r.returncode == 2)
        ok &= caso("sem fontes.json: mensagem de erro", "fontes inexistente" in r.stdout)
    return ok


def test_missing_citaveis_json():
    """RED: sem citaveis.json → exit 2."""
    ok = True
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, NUMERO)
        os.makedirs(os.path.join(ws, "custodia"))
        json.dump({"processo": NUMERO, "versao": 1, "fontes": [FONTE]},
                  open(os.path.join(ws, NUMERO + "-fontes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        # Não cria citaveis.json

        r = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_prancha.py"), ws],
                          capture_output=True, text=True)
        ok &= caso("sem citaveis.json: exit 2", r.returncode == 2)
        ok &= caso("sem citaveis.json: mensagem de erro", "citaveis inexistente" in r.stdout)
    return ok


def test_citavel_ausente_do_fontes():
    """RED: citável listado mas ausente do fontes.json → "AUSENTE DO FONTES.JSON"."""
    ok = True
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, NUMERO)
        os.makedirs(os.path.join(ws, "custodia"))
        json.dump({"processo": NUMERO, "versao": 1, "fontes": [FONTE]},
                  open(os.path.join(ws, NUMERO + "-fontes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({"processo": NUMERO,
                   "fontes": [{"id": "BNP-002", "referencia": "Tema 999",
                               "motivo": "não existe"}],
                   "praxe": []},
                  open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({}, open(os.path.join(ws, "custodia", "proveniencia-cache.json"), "w"))

        r = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_prancha.py"), ws],
                          capture_output=True, text=True)
        ok &= caso("citável ausente: exit 0", r.returncode == 0)
        texto = open(os.path.join(ws, NUMERO + "-conferencia-fontes.md"), encoding="utf-8").read()
        ok &= caso("citável ausente: marca AUSENTE DO FONTES.JSON", "AUSENTE DO FONTES.JSON" in texto)
    return ok


def test_fonte_nao_citavel():
    """RED: fonte listada em fontes.json mas não em citaveis → seção "não citáveis"."""
    ok = True
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, NUMERO)
        os.makedirs(os.path.join(ws, "custodia"))

        fonte2 = FONTE.copy()
        fonte2["id"] = "BNP-002"
        fonte2["referencia"] = "Tema 72"

        json.dump({"processo": NUMERO, "versao": 1, "fontes": [FONTE, fonte2]},
                  open(os.path.join(ws, NUMERO + "-fontes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({"processo": NUMERO,
                   "fontes": [{"id": "BNP-001", "referencia": "Tema 71",
                               "motivo": "objeto"}],
                   "praxe": []},
                  open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({}, open(os.path.join(ws, "custodia", "proveniencia-cache.json"), "w"))

        r = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_prancha.py"), ws],
                          capture_output=True, text=True)
        texto = open(os.path.join(ws, NUMERO + "-conferencia-fontes.md"), encoding="utf-8").read()
        ok &= caso("não citável: seção", "Fontes de análise (não citáveis na minuta)" in texto)
        ok &= caso("não citável: BNP-002 listado", "BNP-002" in texto)
    return ok


def test_cache_vereditos_optional():
    """RED: cache e vereditos são opcionais (graceful)."""
    ok = True
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, NUMERO)
        os.makedirs(os.path.join(ws, "custodia"))
        json.dump({"processo": NUMERO, "versao": 1, "fontes": [FONTE]},
                  open(os.path.join(ws, NUMERO + "-fontes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({"processo": NUMERO,
                   "fontes": [{"id": "BNP-001", "referencia": "Tema 71",
                               "motivo": "objeto"}],
                   "praxe": []},
                  open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        # Não cria cache.json nem vereditos.md

        r = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_prancha.py"), ws],
                          capture_output=True, text=True)
        ok &= caso("sem cache/vereditos: exit 0", r.returncode == 0)
        texto = open(os.path.join(ws, NUMERO + "-conferencia-fontes.md"), encoding="utf-8").read()
        ok &= caso("sem cache: NAO VERIFICADA", "NAO VERIFICADA" in texto)
        ok &= caso("sem vereditos: —", "—" in texto)
    return ok


def test_fonte_com_url():
    """RED: fonte com URL aparece na prancha."""
    ok = True
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, NUMERO)
        os.makedirs(os.path.join(ws, "custodia"))

        fonte_url = FONTE.copy()
        fonte_url["url"] = "https://exemplo.test/jurisprudencia/123"

        json.dump({"processo": NUMERO, "versao": 1, "fontes": [fonte_url]},
                  open(os.path.join(ws, NUMERO + "-fontes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({"processo": NUMERO,
                   "fontes": [{"id": "BNP-001", "referencia": "Tema 71",
                               "motivo": "objeto"}],
                   "praxe": []},
                  open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        json.dump({}, open(os.path.join(ws, "custodia", "proveniencia-cache.json"), "w"))

        r = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_prancha.py"), ws],
                          capture_output=True, text=True)
        texto = open(os.path.join(ws, NUMERO + "-conferencia-fontes.md"), encoding="utf-8").read()
        ok &= caso("URL presente", "https://exemplo.test/jurisprudencia/123" in texto)
    return ok


def main():
    ok = True
    print("=== TESTES RED (ESPERADO FALHAR) ===\n")

    print("Teste 1: _veredito com prefix-boundary")
    ok &= test_veredito_prefix_boundary()
    print()

    print("Teste 2: blockquote multiline")
    ok &= test_multiline_verbatim()
    print()

    print("Teste 3: fontes.json obrigatório")
    ok &= test_missing_fontes_json()
    print()

    print("Teste 4: citaveis.json obrigatório")
    ok &= test_missing_citaveis_json()
    print()

    print("Teste 5: citável ausente do fontes.json")
    ok &= test_citavel_ausente_do_fontes()
    print()

    print("Teste 6: fonte não citável (seção de análise)")
    ok &= test_fonte_nao_citavel()
    print()

    print("Teste 7: cache/vereditos opcionais")
    ok &= test_cache_vereditos_optional()
    print()

    print("Teste 8: URL na fonte")
    ok &= test_fonte_com_url()
    print()

    # Teste legado
    print("Teste 9: caso clássico (legado)")
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, NUMERO)
        os.makedirs(os.path.join(ws, "custodia"))
        json.dump({"processo": NUMERO, "versao": 1, "fontes": [FONTE]},
                  open(os.path.join(ws, NUMERO + "-fontes.json"), "w",
                       encoding="utf-8"), ensure_ascii=False)
        json.dump({"processo": NUMERO,
                   "fontes": [{"id": "BNP-001", "referencia": "Tema 71",
                               "motivo": "objeto do caso",
                               "referencias_equivalentes": ["Tema 71"]}],
                   "praxe": ["Súmula 512"]},
                  open(os.path.join(ws, NUMERO + "-citaveis.json"), "w",
                       encoding="utf-8"), ensure_ascii=False)
        json.dump({chave_fonte(FONTE): {"estado": "CONFIRMADA",
                                        "data": "2026-07-24", "detalhe": ""}},
                  open(os.path.join(ws, "custodia", "proveniencia-cache.json"),
                       "w", encoding="utf-8"))
        with open(os.path.join(ws, NUMERO + "-vereditos-parafrase.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Vereditos de Paráfrase\nREFUTADAS: 0\n\n"
                    "## Tema 71\nVEREDITO: FIEL\n")
        r = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_prancha.py"),
                            ws], capture_output=True, text=True)
        ok &= caso("prancha roda", r.returncode == 0)
        saida = os.path.join(ws, NUMERO + "-conferencia-fontes.md")
        ok &= caso("prancha gravada", os.path.exists(saida))
        texto = open(saida, encoding="utf-8").read()
        ok &= caso("prancha tem referência", "Tema 71" in texto)
        ok &= caso("prancha tem verbatim", "É legítima a revogação" in texto)
        ok &= caso("prancha tem estado", "CONFIRMADA" in texto)
        ok &= caso("prancha tem veredito", "FIEL" in texto)
        ok &= caso("prancha tem praxe", "Súmula 512" in texto)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
