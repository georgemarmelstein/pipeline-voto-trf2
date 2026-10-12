#!/usr/bin/env python3
"""test_verificar_voto.py - Testes do gate do /pipeline-voto (verificar_voto.py).

Fixtures sintéticas pequenas em diretório temporário; o gate roda como CLI
(subprocess), do jeito que o orquestrador o chama.

Roda com: python scripts/test_verificar_voto.py   (saída [OK]/[ERRO]/[FIM])
      ou: python -m pytest scripts/test_verificar_voto.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(AQUI, "verificar_voto.py")
NUMERO = "0000001-11.2026.4.05.8100"

ENCH = ("Texto com acentuação correta: apelação, sentença, réu, decisão, ação, "
        "não, revisão, capítulo, honorários. " * 10)

LINHA_TEMPO = ("# Linha do Tempo Recursal\n\n" + NUMERO + "\n\n## Cronologia\n\n" + ENCH
               + "\n\n## PEÇAS-CHAVE\n\n| Peça | Páginas |\n\n## Quem recorreu e de quê\n\n"
               "O réu apelou do capítulo de mérito.\n\n## Ocorrências no tribunal\n\n"
               "Sem ocorrências localizadas.\n\n## Alertas\n\nSem alertas.\n\n"
               "É o que satisfaz extrair dos autos.\n")
RELATORIO = "RELATÓRIO\n\n" + ENCH + "\n\nÉ o relatório.\n"
PESQ_BNP = "# Pesquisa BNP\n\n" + ENCH + "\n\nPesquisa BNP concluída.\n"
ANALISE_CORPO = ("Vamos começar. Preciso pensar profundamente sobre esse recurso.\n\n"
                 "## Objeto do Julgamento\n\n" + ENCH + "\n\n## Matriz Capítulo x Resultado\n\n"
                 "| 1 | réu | conhecer | negar provimento |\n\n## Consectários Recursais\n\n"
                 "Honorários recursais majorados.\n\n## Observações Fora do Dispositivo\n\n"
                 "Nenhuma.\n\n## Proposta de Dispositivo\n\nNegar provimento.\n")
ANALISE = ANALISE_CORPO + "\nPronto.\n"
ANALISE_ESCALAR = (ANALISE_CORPO + "\nESCALAR: pesquisa\n"
                   "MOTIVO: a solução do capítulo 1 depende de tema cuja vigência não se certifica.\n")
VOTO = ("VOTO\n\n" + ENCH + "\n\nAnte o exposto, conheço da apelação e nego-lhe provimento.\n\n"
        "É como voto.\n")
EMENTA = ("EMENTA\n\nDireito previdenciário. Apelação cível. Revisão de benefício.\n\n"
          "I. CASO EM EXAME\n1. Apelação contra sentença de procedência.\n\n"
          "II. QUESTÃO EM DISCUSSÃO\n2. Saber se é devida a revisão.\n\n"
          "III. RAZÕES DE DECIDIR\n3. " + ENCH + "\n\n"
          "IV. DISPOSITIVO E TESE\n4. Apelação desprovida.\n\n"
          "Dispositivos relevantes citados: CPC, art. 85, § 11.\n[FIM_EMENTA]\n")
ACORDAO = EMENTA.replace("[FIM_EMENTA]\n", "").strip() + "\n\n" + RELATORIO + "\n" + VOTO
COERENCIA_BASE = ("# Conferência de Coerência do Acórdão\n\n## Capítulos devolvidos\n\n" + ENCH
                  + "\n\n## Divergências\n\n")
COERENTE = COERENCIA_BASE + "Nenhuma divergência.\n\nVEREDITO: COERENTE\n"
BLOCOS_2 = ("DIVERGENCIA 1\nRESPONSAVEL: VOTO\nTRECHO: dispositivo.\nMOTIVO: omite honorários.\n\n"
            "DIVERGENCIA 2\nRESPONSÁVEL: EMENTA\nTRECHO: parte IV.\nMOTIVO: declara provimento.\n\n")
DIVERGENTE_2 = COERENCIA_BASE + BLOCOS_2 + "VEREDITO: DIVERGENTE — 2 itens\n"

ROTA_DIRETA = {"rota": [], "desvio": None, "temas_pesquisa": [], "fatos_probatorios": [],
               "justificativa_rotina": "Matéria pacificada em tema com tese firmada; fatos incontroversos."}
ROTA_AMBAS = {"rota": ["pesquisa", "probatica"], "desvio": None,
              "temas_pesquisa": ["auxílio-invalidez na base do adicional natalino"],
              "fatos_probatorios": ["nexo causal disputado no laudo"], "justificativa_rotina": None}
ROTA_PESQUISA = dict(ROTA_AMBAS, rota=["pesquisa"], fatos_probatorios=[])
ROTA_EMBARGOS = {"rota": [], "desvio": "embargos", "temas_pesquisa": [], "fatos_probatorios": [],
                 "justificativa_rotina": "Embargos de declaração opostos contra o acórdão, pendentes."}
ROTA_PREJUDICADO = dict(ROTA_EMBARGOS, desvio="prejudicado",
                        justificativa_rotina="Desistência do recurso noticiada nos autos.")


def triagem(rota, blocos=1):
    bloco = "```json\n" + json.dumps(rota, ensure_ascii=False) + "\n```\n\n"
    return ("# Triagem Recursal\n\n## QUESTÕES IDENTIFICADAS\n\n" + ENCH
            + "\n\n## ADMISSIBILIDADE APARENTE E MATÉRIA DEVOLVIDA\n\nApelação tempestiva.\n\n"
            "## EVIDÊNCIAS\n\nBusca 1 sem resultados.\n\n## ROTA\n\n" + bloco * blocos
            + "Triagem concluída.\n")


# ------------------------------------------------------------------ helpers

def novo_ws():
    raiz = tempfile.mkdtemp(prefix="test_voto_")
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


def rodar(ws, *args):
    return subprocess.run([sys.executable, GATE, ws, *args], capture_output=True,
                          text=True, encoding="utf-8")


def pendentes(saida):
    for linha in saida.splitlines():
        if linha.startswith("PENDENTES: "):
            resto = linha[len("PENDENTES: "):].strip()
            return [] if resto == "(nenhuma)" else resto.split()
    return None


def tronco_ate_triagem(ws, rota):
    grava(ws, "-linha-tempo.md", LINHA_TEMPO)
    grava(ws, "-relatorio.md", RELATORIO)
    grava(ws, "-triagem.md", triagem(rota))


def com_ws(fn):
    def envolvido():
        raiz, ws = novo_ws()
        try:
            fn(ws)
        finally:
            shutil.rmtree(raiz, ignore_errors=True)
    envolvido.__name__ = fn.__name__
    return envolvido


# ------------------------------------------------------------------ testes

@com_ws
def test_varredura_vazia_aguarda_rota(ws):
    r = rodar(ws)
    assert r.returncode == 0
    assert pendentes(r.stdout) == ["linha-tempo", "relatorio", "triagem", "analise", "voto",
                                   "ementa", "acordao", "coerencia"]
    assert "[AGUARDA_ROTA] pesquisa-tribunal" in r.stdout
    assert rodar(ws, "--gate").returncode == 1


@com_ws
def test_ancoras_reais_passam(ws):
    tronco_ate_triagem(ws, ROTA_DIRETA)
    for etapa in ("linha-tempo", "relatorio", "triagem"):
        r = rodar(ws, "--etapa", etapa)
        assert r.returncode == 0, r.stdout


@com_ws
def test_relatorio_com_ancora_da_sentenca_reprova(ws):
    grava(ws, "-relatorio.md", "RELATÓRIO\n\n" + ENCH + "\n\nÉ o que havia de relevante a relatar.\n")
    r = rodar(ws, "--etapa", "relatorio")
    assert r.returncode == 1 and "[INVALIDA] relatorio" in r.stdout


@com_ws
def test_relatorio_com_marcador_interno_reprova(ws):
    grava(ws, "-relatorio.md", "RELATÓRIO\n\n" + ENCH + " [VERIFICAR: data da intimação]\n\n"
                               "É o relatório.\n")
    r = rodar(ws, "--etapa", "relatorio")
    assert r.returncode == 1 and "contaminação de publicação" in r.stdout


@com_ws
def test_rota_direta(ws):
    tronco_ate_triagem(ws, ROTA_DIRETA)
    r = rodar(ws, "--rota")
    linhas = r.stdout.splitlines()
    assert r.returncode == 0
    assert linhas[0] == "ROTA: direta"
    assert linhas[1].startswith("JUSTIFICATIVA: Matéria pacificada")
    v = rodar(ws)
    assert "[NAO_DEVIDA] pesquisa-tribunal (fora da rota)" in v.stdout
    assert "[NAO_DEVIDA] probatica (fora da rota)" in v.stdout
    assert pendentes(v.stdout) == ["analise", "voto", "ementa", "acordao", "coerencia"]


@com_ws
def test_rota_com_trilhos_imprime_temas_e_fatos(ws):
    tronco_ate_triagem(ws, ROTA_AMBAS)
    r = rodar(ws, "--rota")
    assert r.returncode == 0
    assert "ROTA: pesquisa probatica" in r.stdout
    assert "TEMA: auxílio-invalidez na base do adicional natalino" in r.stdout
    assert "FATO: nexo causal disputado no laudo" in r.stdout
    assert pendentes(rodar(ws).stdout)[:3] == ["pesquisa-tribunal", "pesquisa-bnp", "probatica"]


@com_ws
def test_desvio_embargos(ws):
    tronco_ate_triagem(ws, ROTA_EMBARGOS)
    r = rodar(ws, "--rota")
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "DESVIO: embargos"
    v = rodar(ws, "--gate")
    assert v.returncode == 0, v.stdout
    assert "[NAO_DEVIDA] voto (desvio embargos)" in v.stdout
    assert pendentes(v.stdout) == []


@com_ws
def test_desvio_prejudicado_segue_tronco_sem_trilhos(ws):
    tronco_ate_triagem(ws, ROTA_PREJUDICADO)
    r = rodar(ws, "--rota")
    assert r.stdout.splitlines()[:2] == ["DESVIO: prejudicado", "ROTA: direta"]
    assert pendentes(rodar(ws).stdout) == ["analise", "voto", "ementa", "acordao", "coerencia"]


@com_ws
def test_rotas_invalidas(ws):
    casos = [dict(ROTA_PESQUISA, temas_pesquisa=[]),          # pesquisa sem tema
             dict(ROTA_DIRETA, justificativa_rotina=""),       # rotina sem certificação
             dict(ROTA_EMBARGOS, desvio="saneamento"),         # desvio de outro pipeline
             dict(ROTA_EMBARGOS, rota=["pesquisa"], temas_pesquisa=["x"])]  # desvio com trilho
    for dados in casos:
        grava(ws, "-triagem.md", triagem(dados))
        assert rodar(ws, "--rota").returncode == 1, dados
        assert rodar(ws, "--etapa", "triagem").returncode == 1, dados
    grava(ws, "-triagem.md", triagem(ROTA_DIRETA, blocos=2))
    r = rodar(ws, "--rota")
    assert r.returncode == 1 and "exatamente um" in r.stdout


@com_ws
def test_fonte_indisponivel(ws):
    tronco_ate_triagem(ws, ROTA_PESQUISA)
    grava(ws, "-pesquisa-bnp.md", PESQ_BNP)
    grava(ws, "-indisponiveis.txt", "pesquisa-tribunal\n")
    v = rodar(ws, "--etapas", "pesquisa-tribunal,pesquisa-bnp", "--gate")
    assert v.returncode == 0 and "[INDISPONIVEL] pesquisa-tribunal" in v.stdout, v.stdout
    os.remove(os.path.join(ws, NUMERO + "-pesquisa-bnp.md"))
    grava(ws, "-indisponiveis.txt", "pesquisa-tribunal\npesquisa-bnp\n")
    v = rodar(ws, "--etapas", "pesquisa-tribunal,pesquisa-bnp", "--gate")
    assert v.returncode == 1  # as duas fora: trilho sem insumo, continua pendente


@com_ws
def test_analise_ok_e_escalar(ws):
    tronco_ate_triagem(ws, ROTA_DIRETA)
    grava(ws, "-analise.md", ANALISE)
    assert rodar(ws, "--etapa", "analise").returncode == 0
    grava(ws, "-analise.md", ANALISE_ESCALAR)
    r = rodar(ws, "--etapa", "analise")
    assert r.returncode == 3 and r.stdout.startswith("[ESCALAR] analise: pesquisa"), r.stdout
    v = rodar(ws)  # a escalada torna o trilho devido, mesmo fora da rota
    assert pendentes(v.stdout)[:3] == ["pesquisa-tribunal", "pesquisa-bnp", "analise"]
    assert "[NAO_DEVIDA] probatica (fora da rota)" in v.stdout
    grava(ws, "-analise.md", ANALISE_CORPO + "\nESCALAR: doutrina\nMOTIVO: x.\n")
    assert rodar(ws, "--etapa", "analise").returncode == 1
    grava(ws, "-analise.md", ANALISE.replace("## Consectários Recursais", "## Consectários"))
    assert rodar(ws, "--etapa", "analise").returncode == 1


@com_ws
def test_voto_e_ementa(ws):
    grava(ws, "-voto.md", VOTO)
    grava(ws, "-ementa.md", EMENTA)
    assert rodar(ws, "--etapa", "voto").returncode == 0
    assert rodar(ws, "--etapa", "ementa").returncode == 0
    grava(ws, "-ementa.md", EMENTA.replace("[FIM_EMENTA]\n", ""))
    assert rodar(ws, "--etapa", "ementa").returncode == 1
    grava(ws, "-voto.md", VOTO.replace("Ante o exposto, conheço", "**Ante o exposto**, conheço"))
    assert rodar(ws, "--etapa", "voto").returncode == 1


@com_ws
def test_coerencia_coerente_e_divergente(ws):
    grava(ws, "-coerencia.md", COERENTE)
    assert rodar(ws, "--etapa", "coerencia").returncode == 0
    grava(ws, "-coerencia.md", DIVERGENTE_2)
    r = rodar(ws, "--etapa", "coerencia")
    assert r.returncode == 4, r.stdout
    assert "RESPONSAVEL: VOTO (item 1)" in r.stdout
    assert "RESPONSAVEL: EMENTA (item 2)" in r.stdout
    um = COERENCIA_BASE + BLOCOS_2.split("\n\n")[0] + "\n\nVEREDITO: DIVERGENTE — 1 item\n"
    grava(ws, "-coerencia.md", um)
    assert rodar(ws, "--etapa", "coerencia").returncode == 4


@com_ws
def test_coerencia_mal_formada(ws):
    casos = [COERENCIA_BASE + BLOCOS_2 + "VEREDITO: DIVERGENTE — 3 itens\n",     # contagem errada
             COERENCIA_BASE + BLOCOS_2 + "VEREDITO: COERENTE\n",                 # coerente com blocos
             COERENCIA_BASE + "VEREDITO: COERENTE\n\n## Observações\n\nNada.\n",  # não é a última linha
             COERENCIA_BASE + "DIVERGENCIA 1\nTRECHO: x.\nMOTIVO: y.\n\n"
             "VEREDITO: DIVERGENTE — 1 itens\n"]                                  # sem RESPONSAVEL
    for texto in casos:
        grava(ws, "-coerencia.md", texto)
        assert rodar(ws, "--etapa", "coerencia").returncode == 1, texto[-60:]


@com_ws
def test_acordao_resto_de_sinalizador_e_desatualizado(ws):
    grava(ws, "-ementa.md", EMENTA, idade=300)
    grava(ws, "-relatorio.md", RELATORIO, idade=300)
    grava(ws, "-voto.md", VOTO, idade=300)
    grava(ws, "-acordao.md", ACORDAO, idade=200)
    r = rodar(ws, "--etapa", "acordao")
    assert r.returncode == 0, r.stdout
    grava(ws, "-acordao.md", EMENTA.strip() + "\n\n" + RELATORIO + "\n" + VOTO, idade=200)
    r = rodar(ws, "--etapa", "acordao")
    assert r.returncode == 1 and "FIM_EMENTA" in r.stdout
    grava(ws, "-acordao.md", ACORDAO, idade=200)
    grava(ws, "-voto.md", VOTO, idade=100)  # voto regenerado depois do merge
    r = rodar(ws, "--etapa", "acordao")
    assert r.returncode == 1 and "desatualizado" in r.stdout


@com_ws
def test_gate_final_completo(ws):
    tronco_ate_triagem(ws, ROTA_DIRETA)
    grava(ws, "-analise.md", ANALISE)
    grava(ws, "-ementa.md", EMENTA, idade=300)
    grava(ws, "-relatorio.md", RELATORIO, idade=300)
    grava(ws, "-voto.md", VOTO, idade=300)
    grava(ws, "-acordao.md", ACORDAO, idade=200)
    grava(ws, "-coerencia.md", COERENTE, idade=100)
    v = rodar(ws, "--gate")
    assert v.returncode == 0, v.stdout
    assert pendentes(v.stdout) == []
    grava(ws, "-coerencia.md", DIVERGENTE_2, idade=100)
    v = rodar(ws, "--gate")
    assert v.returncode == 1 and pendentes(v.stdout) == ["coerencia"], v.stdout


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
