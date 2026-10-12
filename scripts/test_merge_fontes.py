#!/usr/bin/env python3
"""test_merge_fontes.py - Testes do merge determinístico da cadeia de custódia.

Roda com: python scripts/test_merge_fontes.py
Fixtures sintéticas em tempdir; asserts puros; exit 1 se qualquer caso falhar.
"""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(AQUI, "merge_fontes.py")

TESE = ("Incide correção monetária pelo IPCA-E sobre as condenações da Fazenda "
        "Pública de natureza não tributária.")
TESE2 = ("Compete à Justiça Federal comum processar e julgar as ações que "
         "envolvam interesse jurídico da União.")
TESE3 = ("O prazo prescricional quinquenal aplica-se às ações de cobrança "
         "propostas contra a Fazenda Pública.")

_SEQ = [0]  # cada caso ganha subdiretório próprio — fixtures nunca vazam entre casos


def montar_workspace(d, numero=None):
    _SEQ[0] += 1
    numero = numero or "0000001-11.2026.4.05.8100"
    ws = os.path.join(d, f"caso{_SEQ[0]}", numero)
    os.makedirs(ws)
    return ws, numero


def item(origem_mcp="bnp-api", tribunal="STF", tipo="repercussao-geral",
         referencia="Tema 810", campo="tese", trecho_verbatim=TESE, **kw):
    d = {"origem_mcp": origem_mcp, "tribunal": tribunal, "tipo": tipo,
         "referencia": referencia, "orgao_julgador": None, "data_julgamento": None,
         "campo": campo, "trecho_verbatim": trecho_verbatim, "url": None}
    d.update(kw)
    return d


def escrever_parcial(ws, nome, fontes, envelope=False, numero=None):
    conteudo = fontes
    if envelope:
        conteudo = {"processo": numero or "?", "versao": 1, "fontes": fontes}
    with open(os.path.join(ws, nome), "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False)


def caminho_merge(ws, numero):
    return os.path.join(ws, numero + "-fontes.json")


def rodar(ws, *extra):
    return subprocess.run([sys.executable, GATE, ws, *extra],
                          capture_output=True, text=True)


def caso(nome, cond):
    print(("[OK] " if cond else "[ERRO] ") + nome)
    return cond


def main():
    ok = True
    with tempfile.TemporaryDirectory() as d:
        # a. merge de 2 parciais validos -> exit 0, 3 itens, ids reatribuidos
        ws, numero = montar_workspace(d)
        escrever_parcial(ws, "fontes-bnp.json",
                          [item(referencia="Tema 810", trecho_verbatim=TESE),
                           item(referencia="Tema 905", trecho_verbatim=TESE2)],
                          envelope=True, numero=numero)
        escrever_parcial(ws, "fontes-julia.json",
                          [item(origem_mcp="julia-trf5", tribunal="TRF5", tipo="acordao",
                                referencia="AC 0001", trecho_verbatim=TESE3)])
        r = rodar(ws)
        ok &= caso("merge de 2 parciais: exit 0", r.returncode == 0)
        caminho = caminho_merge(ws, numero)
        ok &= caso("merge de 2 parciais: arquivo criado", os.path.exists(caminho))
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        ok &= caso("merge de 2 parciais: 3 itens", len(dados.get("fontes", [])) == 3)
        ids = {fonte["id"] for fonte in dados.get("fontes", [])}
        ok &= caso("merge de 2 parciais: ids reatribuidos",
                   ids == {"BNP-001", "BNP-002", "JULIA-001"})
        ok &= caso("merge de 2 parciais: processo == id do workspace",
                   dados.get("processo") == numero)
        ok &= caso("merge de 2 parciais: versao == 1", dados.get("versao") == 1)

        # b. origem_mcp fora da whitelist -> exit 1, rejeicao nomeada, validas sobrevivem
        ws, numero = montar_workspace(d)
        escrever_parcial(ws, "fontes-bnp.json",
                          [item(referencia="Tema 810", trecho_verbatim=TESE)])
        escrever_parcial(ws, "fontes-cjf.json",
                          [item(origem_mcp="google", tribunal="STF",
                                referencia="X", trecho_verbatim=TESE2)])
        r = rodar(ws)
        ok &= caso("origem nao autorizada: exit 1", r.returncode == 1)
        ok &= caso("origem nao autorizada: nomeada no stdout", "google" in r.stdout)
        caminho = caminho_merge(ws, numero)
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        ok &= caso("origem nao autorizada: valida sobrevive",
                   len(dados.get("fontes", [])) == 1
                   and dados["fontes"][0]["referencia"] == "Tema 810")

        # c. duplicata exata (mesma origem+referencia+trecho, espaco/caixa diferentes)
        ws, numero = montar_workspace(d)
        trecho_duplicado = "  " + TESE.upper().replace(" ", "  ") + "  "
        escrever_parcial(ws, "fontes-bnp.json",
                          [item(origem_mcp="bnp-api", referencia="Tema 810",
                                trecho_verbatim=TESE)])
        escrever_parcial(ws, "fontes-cjf.json",
                          [item(origem_mcp="bnp-api", referencia="Tema 810",
                                trecho_verbatim=trecho_duplicado)])
        r = rodar(ws)
        ok &= caso("duplicata: exit 0", r.returncode == 0)
        caminho = caminho_merge(ws, numero)
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        ok &= caso("duplicata: deduplicado para 1 item", len(dados.get("fontes", [])) == 1)
        ok &= caso("duplicata: [FIM] reporta 1 duplicata", "1 duplicata" in r.stdout)

        # d. trecho_verbatim vazio -> exit 1, rejeitado, irmaos validos sobrevivem
        ws, numero = montar_workspace(d)
        escrever_parcial(ws, "fontes-bnp.json",
                          [item(referencia="Tema 810", trecho_verbatim=TESE),
                           item(referencia="Tema 999", trecho_verbatim="")])
        r = rodar(ws)
        ok &= caso("trecho vazio: exit 1", r.returncode == 1)
        caminho = caminho_merge(ws, numero)
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        ok &= caso("trecho vazio: valido sobrevive",
                   len(dados.get("fontes", [])) == 1
                   and dados["fontes"][0]["referencia"] == "Tema 810")

        # e. nenhum parcial encontrado -> exit 0, aviso, sem criar arquivo
        ws, numero = montar_workspace(d)
        r = rodar(ws)
        ok &= caso("sem parciais: exit 0", r.returncode == 0)
        ok &= caso("sem parciais: aviso no stdout", "[AVISO]" in r.stdout)
        caminho = caminho_merge(ws, numero)
        ok &= caso("sem parciais: arquivo NAO criado", not os.path.exists(caminho))

        # f. fontes-triagem.json com origem_mcp real -> prefixo pela origem, nao pelo nome do arquivo
        ws, numero = montar_workspace(d)
        escrever_parcial(ws, "fontes-triagem.json",
                          [item(origem_mcp="bnp-api", referencia="Tema 810",
                                trecho_verbatim=TESE)])
        r = rodar(ws)
        ok &= caso("triagem: exit 0", r.returncode == 0)
        caminho = caminho_merge(ws, numero)
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        ok &= caso("triagem: prefixo BNP pela origem_mcp declarada",
                   len(dados.get("fontes", [])) == 1
                   and dados["fontes"][0]["id"] == "BNP-001")

        # g. origens do radar dos TRFs (pipeline-voto) -> aceitas, prefixo proprio
        ws, numero = montar_workspace(d)
        escrever_parcial(ws, "fontes-tribunal.json",
                          [item(origem_mcp="trf4-eproc", tribunal="TRF4", tipo="acordao",
                                referencia="5000001-11.2025.4.04.7000", campo="ementa",
                                trecho_verbatim=TESE2),
                           item(origem_mcp="trf1-cjf", tribunal="TRF1", tipo="acordao",
                                referencia="1000001-11.2024.4.01.3400", campo="ementa",
                                trecho_verbatim=TESE3)])
        r = rodar(ws)
        ok &= caso("radar TRFs: exit 0", r.returncode == 0)
        with open(caminho_merge(ws, numero), encoding="utf-8") as f:
            ids = sorted(x["id"] for x in json.load(f).get("fontes", []))
        ok &= caso("radar TRFs: prefixos TRF1CJF e TRF4",
                   ids == ["TRF1CJF-001", "TRF4-001"])

    print("[FIM] " + ("todos os casos OK" if ok else "HA FALHAS"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
