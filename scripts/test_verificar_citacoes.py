#!/usr/bin/env python3
"""test_verificar_citacoes.py - Testes do gate de citações verbatim.

Roda com: python scripts/test_verificar_citacoes.py
Fixtures sintéticas em tempdir; asserts puros; exit 1 se qualquer caso falhar.
"""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(AQUI, "verificar_citacoes.py")

TESE = ("Incide correção monetária pelo IPCA-E sobre as condenações da Fazenda "
        "Pública de natureza não tributária, conforme decidido no julgamento paradigma.")
DEPOIMENTO = ("o depoente afirmou que trabalhou na lavoura de cana entre março de 1990 "
              "e dezembro de 1994 sem registro em carteira")

_SEQ = [0]  # cada caso ganha subdiretório próprio — fixtures nunca vazam entre casos


def montar_workspace(d, doc_texto, com_fontes=True):
    _SEQ[0] += 1
    numero = "0000001-11.2026.4.05.8100"
    ws = os.path.join(d, f"caso{_SEQ[0]}", numero)
    os.makedirs(ws)
    with open(os.path.join(ws, "processo.txt"), "w", encoding="utf-8") as f:
        f.write("Autos simulados. Em audiência, " + DEPOIMENTO + ". Nada mais.")
    if com_fontes:
        fontes = {"processo": numero, "versao": 1, "fontes": [{
            "id": "BNP-001", "origem_mcp": "bnp-api", "tribunal": "STF",
            "tipo": "repercussao-geral", "referencia": "Tema 810",
            "orgao_julgador": None, "data_julgamento": None,
            "campo": "tese", "trecho_verbatim": TESE, "url": None}]}
        with open(os.path.join(ws, numero + "-fontes.json"), "w", encoding="utf-8") as f:
            json.dump(fontes, f, ensure_ascii=False)
    with open(os.path.join(ws, numero + "-fundamentacao.md"), "w", encoding="utf-8") as f:
        f.write(doc_texto)
    return ws


def rodar(ws, *extra):
    return subprocess.run([sys.executable, GATE, ws, *extra],
                          capture_output=True, text=True)


def caso(nome, cond):
    print(("[OK] " if cond else "[ERRO] ") + nome)
    return cond


def main():
    ok = True
    with tempfile.TemporaryDirectory() as d:
        # 1. Citação exata da fonte -> exit 0
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\n\nComo fixado: "%s". Aplico.\nJUIZ FEDERAL' % TESE)
        ok &= caso("citacao exata da fonte passa", rodar(ws).returncode == 0)
        # 2. Citação com acentos/caixa divergentes -> ainda passa (normalização)
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\n"%s". Aplico.\nJUIZ FEDERAL' % TESE.upper())
        ok &= caso("normalizacao de caixa/acento", rodar(ws).returncode == 0)
        # 3. Citação inventada (nao consta de fonte nem autos) -> exit 1
        falsa = ("O direito adquirido prevalece sobre qualquer alteração normativa "
                 "posterior em matéria de vencimentos de servidores públicos federais.")
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\n"%s"\nJUIZ FEDERAL' % falsa)
        r = rodar(ws)
        ok &= caso("citacao inventada reprova", r.returncode == 1 and "[ERRO]" in r.stdout)
        # 4. Citação dos autos (depoimento) -> passa mesmo sem constar de fontes.json
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\nA testemunha disse que "%s".\nJUIZ FEDERAL' % DEPOIMENTO)
        ok &= caso("citacao dos autos passa", rodar(ws).returncode == 0)
        # 5. Citação com corte interno (...) -> cada fragmento longo confere
        cortada = TESE[:70] + " (...) " + TESE[-60:]
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\n"%s"\nJUIZ FEDERAL' % cortada)
        ok &= caso("corte interno (...) passa", rodar(ws).returncode == 0)
        # 6. Aspas curtas (expressao idiomatica) sao ignoradas
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\nAplica-se o "in dubio pro reo" aqui.\nJUIZ FEDERAL')
        ok &= caso("aspas curtas ignoradas", rodar(ws).returncode == 0)
        # 7. Sem fontes.json: cita jurisprudencia entre aspas -> reprova (corpus = so autos)
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\n"%s"\nJUIZ FEDERAL' % TESE, com_fontes=False)
        ok &= caso("sem fontes.json, tese reprovada", rodar(ws).returncode == 1)
        # 8. Aspas tipograficas brasileiras (U+201C/U+201D de verdade — cobre o 2º ramo do RE_ASPAS)
        # Exige "1/1 conferidas" no stdout: regex quebrado que ignora a citação daria
        # exit 0 vácuo (0/0) e passaria despercebido se só o returncode fosse checado.
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\nComo fixado: “%s”.\nJUIZ FEDERAL' % TESE)
        r = rodar(ws)
        ok &= caso("aspas tipograficas", r.returncode == 0 and "1/1 conferidas" in r.stdout)
        # 9/10. --ignorar-apos: citacao valida + auto-citacao inventada no Log de
        # Alteracoes (achado T3: 26 falsos positivos num documento real) — com a flag,
        # o HEADING "## Log de Alterações" trunca (exit 0); sem a flag, reprova (exit 1).
        # A mencao ao marcador em TEXTO CORRIDO antes da citacao valida NAO pode truncar:
        # se truncasse, a valida sairia do regime e o stdout diria "0/0" em vez de "1/1".
        auto_citacao = ("Trecho registrado apenas no histórico de edições da minuta "
                        "robustecida, sem correspondência com fontes ou autos do processo.")
        ws = montar_workspace(d, 'FUNDAMENTAÇÃO\nAs mudanças constam do log de alterações '
                                 'ao final.\nComo fixado: "%s".\n\n'
                                 '## Log de Alterações\n\n**Trecho original:**\n> "%s"\n'
                                 'JUIZ FEDERAL' % (TESE, auto_citacao))
        r_sem = rodar(ws)
        r_com = rodar(ws, "--ignorar-apos=log de alterações")
        ok &= caso("--ignorar-apos trunca no heading do log",
                   r_sem.returncode == 1 and r_com.returncode == 0
                   and "truncado" in r_com.stdout)
        ok &= caso("mencao ao marcador em texto corrido nao trunca",
                   "1/1 conferidas" in r_com.stdout)
        # --fontes: corpus médico alternativo confere citação do parecer
        with tempfile.TemporaryDirectory() as d2:
            numero = "0000002-11.2026.4.05.8100"
            ws2 = os.path.join(d2, numero)
            os.makedirs(ws2)
            trecho = ("Delay in revascularization beyond 14 days was associated "
                      "with a significantly higher major amputation rate.")
            fontes_med = {"caso": numero, "versao": 1, "cobertura": {},
                          "fontes": [{"id": "PUBMED-001", "trecho_verbatim": trecho}]}
            with open(os.path.join(ws2, numero + "-fontes-medicas.json"),
                      "w", encoding="utf-8") as f:
                json.dump(fontes_med, f, ensure_ascii=False)
            with open(os.path.join(ws2, numero + "-parecer-medico.md"),
                      "w", encoding="utf-8") as f:
                f.write('# PARECER\nA literatura registra: "' + trecho + '".\n')
            r = subprocess.run(
                [sys.executable, GATE, ws2, "--doc=-parecer-medico.md",
                 "--fontes=-fontes-medicas.json"],
                capture_output=True, text=True)
            ok &= caso("--fontes confere citação médica exit 0",
                       r.returncode == 0 and "1/1 conferidas" in r.stdout)
    print("[FIM] " + ("todos os casos OK" if ok else "HA FALHAS"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
