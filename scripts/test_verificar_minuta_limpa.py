#!/usr/bin/env python3
"""test_verificar_minuta_limpa.py - Gate v2 da minuta (regime de redação limpa).

Roda com: python scripts/test_verificar_minuta_limpa.py
"""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(AQUI, "verificar_minuta_limpa.py")
NUMERO = "0000001-11.2026.4.05.8100"
_SEQ = [0]

CITAVEIS = {"processo": NUMERO,
            "fontes": [{"id": "BNP-001", "referencia": "Tema 71",
                        "motivo": "precedente sobre o objeto",
                        "referencias_equivalentes": ["Tema 71", "RE 377.457",
                                                     "Súmula Vinculante 62"]}],
            "praxe": ["Súmula 512", "Súmula 105"]}

CABECALHO = "RELATÓRIO\n\nA parte cita o REsp 999.999 e afirma: \"texto transcrito no relatório é livre porque é relato\".\n\nFUNDAMENTAÇÃO\n\n"


def montar(d, corpo, com_vereditos=None):
    _SEQ[0] += 1
    ws = os.path.join(d, f"caso{_SEQ[0]}", NUMERO)
    os.makedirs(ws)
    with open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8") as f:
        json.dump(CITAVEIS, f, ensure_ascii=False)
    with open(os.path.join(ws, NUMERO + "-sentenca.md"), "w", encoding="utf-8") as f:
        f.write(CABECALHO + corpo + "\n\nDISPOSITIVO\n\nJUIZ FEDERAL\n")
    if com_vereditos is not None:
        with open(os.path.join(ws, NUMERO + "-vereditos-parafrase.md"), "w",
                  encoding="utf-8") as f:
            f.write(f"# Vereditos de Paráfrase\nREFUTADAS: {com_vereditos}\n")
    return ws


def rodar(ws, *extra):
    return subprocess.run([sys.executable, GATE, ws, "--doc=-sentenca.md", *extra],
                          capture_output=True, text=True, encoding='utf-8')


def caso(nome, cond):
    print(("[OK] " if cond else "[ERRO] ") + nome)
    return cond


def main():
    ok = True
    with tempfile.TemporaryDirectory() as d:
        # 1. prosa limpa referenciando citável e praxe -> exit 0
        ws = montar(d, "Aplico a ratio do Tema 71 e do RE 377.457. Sem honorários "
                       "(Súmula 512 e Súmula 105).")
        ok &= caso("minuta limpa passa", rodar(ws).returncode == 0)
        # 2. bloco de 20 palavras entre aspas na fundamentação -> exit 1
        ws = montar(d, 'Como firmado: "É legítima a revogação da isenção estabelecida '
                       'no artigo sexto da Lei Complementar setenta pelo artigo '
                       'cinquenta e seis da lei ordinária posterior".')
        ok &= caso("aspas longas reprovam", rodar(ws).returncode == 1)
        # 3. aspas no RELATÓRIO não contam (gate começa em FUNDAMENTAÇÃO)
        ws = montar(d, "Fundamentação em prosa própria, sem citações.")
        ok &= caso("aspas do relatório ficam fora", rodar(ws).returncode == 0)
        # 4. referência fora da lista -> exit 1
        ws = montar(d, "Aplico o Tema 999 da repercussão geral.")
        ok &= caso("referência fora dos citáveis reprova", rodar(ws).returncode == 1)
        # 5. aspas curtas (< 6 palavras) -> passa com aviso
        ws = montar(d, 'O documento "Perguntas e Respostas" da Receita orienta a retenção.')
        r = rodar(ws)
        ok &= caso("aspas curtas passam com aviso",
                   r.returncode == 0 and "[AVISO]" in r.stdout)
        # 6. vereditos: REFUTADAS: 1 -> exit 1; REFUTADAS: 0 -> exit 0
        ws = montar(d, "Aplico a ratio do Tema 71.", com_vereditos=1)
        ok &= caso("veredito refutado reprova", rodar(ws).returncode == 1)
        ws = montar(d, "Aplico a ratio do Tema 71.", com_vereditos=0)
        ok &= caso("vereditos zerados passam", rodar(ws).returncode == 0)
        # 7. --exigir-vereditos sem arquivo -> exit 1
        ws = montar(d, "Aplico a ratio do Tema 71.")
        ok &= caso("--exigir-vereditos sem arquivo reprova",
                   rodar(ws, "--exigir-vereditos").returncode == 1)
        # 8. aspas curly (U+201C/D) com 20 palavras -> exit 1
        texto_longo = "“É legítima a revogação da isenção estabelecida no artigo sexto da Lei Complementar setenta pelo artigo cinquenta e seis”"
        ws = montar(d, f"Conforme decidido: {texto_longo}.")
        ok &= caso("aspas curly longas reprovam", rodar(ws).returncode == 1)
        # 9. aspas curly (U+201C/D) com 3 palavras -> passa com aviso
        texto_curto = "“Perguntas e Respostas”"
        ws = montar(d, f"O documento {texto_curto} da Receita orienta.")
        r = rodar(ws)
        ok &= caso("aspas curly curtas passam com aviso",
                   r.returncode == 0 and "[AVISO]" in r.stdout)
        # 10. citaveis.json malformado (JSON inválido) -> exit 2, sem traceback
        _SEQ[0] += 1
        ws = os.path.join(d, f"caso{_SEQ[0]}", NUMERO)
        os.makedirs(ws)
        with open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8") as f:
            f.write("{invalid")  # JSON malformado
        with open(os.path.join(ws, NUMERO + "-sentenca.md"), "w", encoding="utf-8") as f:
            f.write(CABECALHO + "Aplico a ratio do Tema 71.\n\nDISPOSITIVO\n\nJUIZ FEDERAL\n")
        r = rodar(ws)
        ok &= caso("citaveis.json malformado exit 2",
                   r.returncode == 2 and "citaveis.json inválido" in r.stdout
                   and "Traceback" not in r.stderr)
        # 11. referência duplicada (Tema 999 duas vezes) -> uma [ERRO] apenas
        ws = montar(d, "O Tema 999 e também o Tema 999 são controversos.")
        r = rodar(ws)
        erro_lines = [l for l in r.stdout.split('\n') if "[ERRO]" in l and "Tema 999" in l]
        ok &= caso("referência duplicada dedupada",
                   len(erro_lines) == 1)
        # 12. decisão interlocutória abre com FUNDAMENTO: o relatório fica fora
        ws = os.path.join(d, "caso_fundamento", NUMERO)
        os.makedirs(ws)
        with open(os.path.join(ws, NUMERO + "-citaveis.json"), "w",
                  encoding="utf-8") as f:
            json.dump(CITAVEIS, f, ensure_ascii=False)
        with open(os.path.join(ws, NUMERO + "-sentenca.md"), "w",
                  encoding="utf-8") as f:
            f.write("DECISÃO\n\nA parte invoca o Tema 999 na inicial.\n\n"
                    "É o relatório.\n\nFUNDAMENTO\n\n"
                    "Passo a sanear o feito.\n\nDISPOSITIVO\n\nJUIZ FEDERAL\n")
        r = rodar(ws)
        ok &= caso("marcador FUNDAMENTO reconhecido (relatório fora do gate)",
                   r.returncode == 0 and "não achado" not in r.stdout)
        # 13. FUNDAMENTO não pode recortar cedo demais em minuta de sentença
        ws = montar(d, "Fundamentação limpa, sem referências.")
        with open(os.path.join(ws, NUMERO + "-sentenca.md"), encoding="utf-8") as f:
            texto = f.read()
        with open(os.path.join(ws, NUMERO + "-sentenca.md"), "w",
                  encoding="utf-8") as f:
            f.write(texto.replace("RELATÓRIO\n",
                                  "RELATÓRIO\n\nFUNDAMENTO da pretensão: Tema 999.\n"))
        ok &= caso("prosa iniciada por FUNDAMENTO não vira marcador",
                   rodar(ws).returncode == 0)
        # 14. negrito markdown como subtítulo -> exit 1 (contaminação de publicação)
        ws = montar(d, "**Do direito aplicável**\n\nFundamentação em prosa própria.")
        r = rodar(ws)
        ok &= caso("negrito markdown reprova",
                   r.returncode == 1 and "contaminação de publicação" in r.stdout)
        # 15. itálico markdown -> exit 1
        ws = montar(d, "*Da força maior e da proporcionalidade.* A tese não se sustenta.")
        r = rodar(ws)
        ok &= caso("itálico markdown reprova",
                   r.returncode == 1 and "contaminação de publicação" in r.stdout)
        # 16. título (#), lista (-) e sinalizador ESCALAR: -> exit 1
        ws = montar(d, "# Do mérito\n\n- primeiro ponto\n\nESCALAR: probatica")
        r = rodar(ws)
        ok &= caso("título, lista e ESCALAR reprovam",
                   r.returncode == 1
                   and sum("contaminação de publicação" in l for l in r.stdout.splitlines()) >= 3)
        # 17. markdown no RELATÓRIO também reprova (o documento inteiro é publicação)
        _SEQ[0] += 1
        ws = os.path.join(d, f"caso{_SEQ[0]}", NUMERO)
        os.makedirs(ws)
        with open(os.path.join(ws, NUMERO + "-citaveis.json"), "w", encoding="utf-8") as f:
            json.dump(CITAVEIS, f, ensure_ascii=False)
        with open(os.path.join(ws, NUMERO + "-sentenca.md"), "w", encoding="utf-8") as f:
            f.write("RELATÓRIO\n\n**Síntese** da demanda.\n\nFUNDAMENTAÇÃO\n\n"
                    "Prosa limpa.\n\nDISPOSITIVO\n\nJUIZ FEDERAL\n")
        ok &= caso("markdown no relatório também reprova", rodar(ws).returncode == 1)
        # 18. travessão e asterisco isolado NÃO reprovam (sem falso positivo)
        ws = montar(d, "A sanção — aplicada em 2023 — persiste. Nota de rodapé * não é itálico.")
        ok &= caso("prosa com travessão passa", rodar(ws).returncode == 0)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
