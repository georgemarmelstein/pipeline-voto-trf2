#!/usr/bin/env python3
"""test_merge_voto.py - Testes do merge determinístico do acórdão (merge_voto.py).

Fixtures sintéticas pequenas em diretório temporário; o merge e o gate rodam como
CLI (subprocess), do jeito que o orquestrador os chama.

Roda com: python scripts/test_merge_voto.py   (saída [OK]/[ERRO]/[FIM])
      ou: python -m pytest scripts/test_merge_voto.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
MERGE = os.path.join(AQUI, "merge_voto.py")
GATE = os.path.join(AQUI, "verificar_voto.py")
NUMERO = "0000002-22.2026.4.04.7100"

ENCH = ("Texto com acentuação correta: apelação, sentença, réu, decisão, ação, "
        "não, revisão, capítulo, honorários. " * 10)
RELATORIO = "RELATÓRIO\n\n" + ENCH + "\n\nÉ o relatório.\n"
VOTO = ("VOTO\n\n" + ENCH + "\n\nAnte o exposto, conheço da apelação e nego-lhe provimento.\n\n"
        "É como voto.\n")
EMENTA_CORPO = ("EMENTA\n\nDireito administrativo. Apelação cível. Servidor público.\n\n"
                "I. CASO EM EXAME\n1. Apelação contra sentença de improcedência.\n\n"
                "II. QUESTÃO EM DISCUSSÃO\n2. Saber se é devida a gratificação.\n\n"
                "III. RAZÕES DE DECIDIR\n3. " + ENCH + "\n\n"
                "IV. DISPOSITIVO E TESE\n4. Apelação desprovida.\n\n"
                "Dispositivos relevantes citados: CPC, art. 85, § 11.")
EMENTA = EMENTA_CORPO + "\n[FIM_EMENTA]\n"


def novo_ws():
    raiz = tempfile.mkdtemp(prefix="test_merge_voto_")
    ws = os.path.join(raiz, NUMERO)
    os.makedirs(ws)
    return raiz, ws


def grava(ws, sufixo, texto, idade=None):
    caminho = os.path.join(ws, NUMERO + sufixo)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    if idade is not None:  # segundos no passado (nunca no futuro)
        t = time.time() - idade
        os.utime(caminho, (t, t))
    return caminho


def ler(ws, sufixo):
    with open(os.path.join(ws, NUMERO + sufixo), encoding="utf-8") as f:
        return f.read()


def rodar(script, ws, *args):
    return subprocess.run([sys.executable, script, ws, *args], capture_output=True,
                          text=True, encoding="utf-8")


def entradas(ws, ementa=EMENTA, idade=300):
    grava(ws, "-ementa.md", ementa, idade)
    grava(ws, "-relatorio.md", RELATORIO, idade)
    grava(ws, "-voto.md", VOTO, idade)


def com_ws(fn):
    def envolvido():
        raiz, ws = novo_ws()
        try:
            fn(ws)
        finally:
            shutil.rmtree(raiz, ignore_errors=True)
    envolvido.__name__ = fn.__name__
    return envolvido


@com_ws
def test_merge_valido_monta_na_ordem_e_remove_sinalizador(ws):
    entradas(ws)
    r = rodar(MERGE, ws)
    assert r.returncode == 0, r.stdout
    assert r.stdout.startswith("[OK] acordao -> ")
    texto = ler(ws, "-acordao.md")
    assert texto.startswith("EMENTA\n")
    assert "[FIM_EMENTA]" not in texto
    assert texto.index("IV. DISPOSITIVO E TESE") < texto.index("RELATÓRIO") < texto.index("\nVOTO\n")
    assert texto.endswith("É como voto.\n")
    assert rodar(GATE, ws, "--etapa", "acordao").returncode == 0


@com_ws
def test_merge_idempotente(ws):
    entradas(ws)
    assert rodar(MERGE, ws).returncode == 0
    primeiro = ler(ws, "-acordao.md")
    assert rodar(MERGE, ws).returncode == 0
    assert ler(ws, "-acordao.md") == primeiro


@com_ws
def test_sinalizador_colado_na_ultima_linha(ws):
    entradas(ws, ementa=EMENTA_CORPO + " [FIM_EMENTA]\n")
    assert rodar(MERGE, ws).returncode == 0
    texto = ler(ws, "-acordao.md")
    assert "[FIM_EMENTA]" not in texto
    assert "art. 85, § 11.\n\nRELATÓRIO" in texto


@com_ws
def test_entrada_ausente_nao_grava(ws):
    grava(ws, "-ementa.md", EMENTA)
    grava(ws, "-relatorio.md", RELATORIO)
    r = rodar(MERGE, ws)
    assert r.returncode == 1 and "[ERRO] entrada voto ausente" in r.stdout
    assert not os.path.exists(os.path.join(ws, NUMERO + "-acordao.md"))


@com_ws
def test_entrada_invalida_aponta_a_etapa(ws):
    entradas(ws, ementa=EMENTA_CORPO + "\n")  # ementa sem [FIM_EMENTA]
    r = rodar(MERGE, ws)
    assert r.returncode == 1 and "[ERRO] entrada ementa inválida" in r.stdout


@com_ws
def test_remerge_depois_de_regenerar_o_voto(ws):
    entradas(ws)
    assert rodar(MERGE, ws).returncode == 0
    caminho = os.path.join(ws, NUMERO + "-acordao.md")
    t = time.time() - 200  # acórdão envelhece; voto "regenerado" fica mais novo
    os.utime(caminho, (t, t))
    grava(ws, "-voto.md", VOTO.replace("nego-lhe provimento", "dou-lhe parcial provimento"),
          idade=100)
    r = rodar(GATE, ws, "--etapa", "acordao")
    assert r.returncode == 1 and "desatualizado" in r.stdout
    assert rodar(MERGE, ws).returncode == 0
    assert "dou-lhe parcial provimento" in ler(ws, "-acordao.md")
    assert rodar(GATE, ws, "--etapa", "acordao").returncode == 0


def _rodar_todos():
    testes = [(n, f) for n, f in sorted(globals().items())
              if n.startswith("test_") and callable(f)]
    falhas = []
    for nome, fn in testes:
        try:
            fn()
            print(f"[OK] {nome}")
        except Exception as e:  # noqa: BLE001 — o runner reporta qualquer falha
            print(f"[ERRO] {nome}: {type(e).__name__}: {e}")
            falhas.append(nome)
    print(f"[FIM] {len(testes) - len(falhas)}/{len(testes)} OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(_rodar_todos())
