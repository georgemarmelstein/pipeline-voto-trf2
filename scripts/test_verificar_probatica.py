#!/usr/bin/env python3
"""test_verificar_probatica.py - Testes do gate do tribunal adversarial (anti-capitulação).

Fixtures sintéticas em diretório temporário; asserts puros; saída [OK]/[ERRO]/[FIM].
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verificar_pipeline import verificar_etapa
from verificar_probatica import ETAPAS

RAIZ = tempfile.mkdtemp(prefix="test_probatica_")
_SEQ = [0]  # cada caso ganha subdiretório próprio — fixtures nunca vazam entre casos
FALHAS = []


def caso(nome):
    _SEQ[0] += 1
    d = os.path.join(RAIZ, f"caso{_SEQ[0]:02d}")
    os.makedirs(d)
    return d


def grava(ws, sufixo, texto):
    with open(os.path.join(ws, f"PROC{sufixo}"), "w", encoding="utf-8") as f:
        f.write(texto)


def checa(nome, cond):
    if cond:
        print(f"[OK] {nome}")
    else:
        print(f"[ERRO] {nome}")
        FALHAS.append(nome)


# corpo mínimo válido: >500 chars, com acentos
ENCHIMENTO = ("Análise probatória com acentuação correta: ação, decisão, réu, "
              "convicção, não, síntese, probanda, álibi, perícia. " * 12)

REPLICA_SEM_FIDELIDADE = (
    "# Réplica Pró-Réu\n\n## Ataques\n" + ENCHIMENTO +
    "\n## Concessões Honestas\nNada a conceder.\n\nRéplica pró-réu concluída.\n")

REPLICA_COM_FIDELIDADE = (
    "# Réplica Pró-Réu\n\n## Ataques\n" + ENCHIMENTO +
    "\n## Fidelidade à Tese\n| Probanda contestada | Posição | Razão |\n"
    "|---|---|---|\n| autoria fato 1 | MANTIDA | contraprova de álibi segue de pé |\n"
    "\n## Concessões Honestas\nNada a conceder.\n\nRéplica pró-réu concluída.\n")

CONSOLIDADO_LENTES = (
    "# SÍNTESE PROBATÓRIA CONSOLIDADA\n\n## Pontos de Convergência\n"
    "Convergências genuínas entre as partes:\n" + ENCHIMENTO +
    "\nSíntese probatória consolidada concluída.\n")

CONSOLIDADO_ADVERSARIAL = (
    "# SÍNTESE PROBATÓRIA CONSOLIDADA\n\n## Pontos de Convergência\n"
    "Convergências genuínas entre as partes:\n" + ENCHIMENTO +
    "\n### Consistência Tese-Réplica\nLado pró-réu: consistente.\n"
    "\n## Síntese por Probanda\n| Probanda | Prova | Contraprova | Força | Ônus | Resultado |\n"
    "\nSíntese probatória consolidada concluída.\n")

# 1. réplica SEM seção Fidelidade à Tese → INVÁLIDA
ws = caso("replica-sem-fidelidade")
grava(ws, "-replica-pro-reu.md", REPLICA_SEM_FIDELIDADE)
r = verificar_etapa(ws, "PROC", "replica-pro-reu", ETAPAS)
checa("réplica sem 'Fidelidade à Tese' reprova", r is not None and len(r) > 0)

# 2. réplica COM a seção → VÁLIDA
ws = caso("replica-com-fidelidade")
grava(ws, "-replica-pro-reu.md", REPLICA_COM_FIDELIDADE)
r = verificar_etapa(ws, "PROC", "replica-pro-reu", ETAPAS)
checa("réplica com 'Fidelidade à Tese' passa", r == [])

# 3. espelho pró-autor
ws = caso("replica-pro-autor")
grava(ws, "-replica-pro-autor.md",
      REPLICA_COM_FIDELIDADE.replace("Pró-Réu", "Pró-Autor").replace("pró-réu", "pró-autor"))
r = verificar_etapa(ws, "PROC", "replica-pro-autor", ETAPAS)
checa("réplica pró-autor com a seção passa", r == [])

# 4. consolidado das LENTES continua passando na etapa 'consolidado' (sem regressão)
ws = caso("consolidado-lentes")
grava(ws, "-probatica-consolidado.md", CONSOLIDADO_LENTES)
r = verificar_etapa(ws, "PROC", "consolidado", ETAPAS)
checa("consolidado (lentes) segue válido na etapa 'consolidado'", r == [])

# 5. o MESMO arquivo das lentes REPROVA na etapa 'consolidado-adversarial'
r = verificar_etapa(ws, "PROC", "consolidado-adversarial", ETAPAS)
checa("consolidado sem contraprova/consistência reprova no adversarial",
      r is not None and len(r) > 0)

# 6. consolidado adversarial completo passa
ws = caso("consolidado-adversarial")
grava(ws, "-probatica-consolidado.md", CONSOLIDADO_ADVERSARIAL)
r = verificar_etapa(ws, "PROC", "consolidado-adversarial", ETAPAS)
checa("consolidado adversarial completo passa", r == [])

shutil.rmtree(RAIZ, ignore_errors=True)
print(f"[FIM] {6 - len(FALHAS)}/6 OK" + (f" — FALHAS: {', '.join(FALHAS)}" if FALHAS else ""))
sys.exit(1 if FALHAS else 0)
