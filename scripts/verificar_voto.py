#!/usr/bin/env python3
"""verificar_voto.py - Gate determinístico do /pipeline-voto (padrão v3.0).

Acórdão de 2º grau (TRF1 a TRF6): linha do tempo recursal -> relatório ->
triagem recursal -> [trilhos condicionais: pesquisa-tribunal + pesquisa-bnp,
probatica] -> análise recursal -> voto -> ementa -> acórdão (merge_voto.py) ->
conferência de coerência.

Importa o motor scripts/verificar_pipeline.py (âncoras normalizadas de
acento/caixa dos dois lados) e acrescenta só o que o motor não conhece:

  - CONDICIONAIS (pesquisa-tribunal, pesquisa-bnp, probatica): contam quando a
    ROTA da triagem as pede, quando a análise ESCALOU para o trilho ou quando o
    artefato já existe. Fora disso aparecem como [NAO_DEVIDA]; antes de haver
    triagem válida, como [AGUARDA_ROTA]. Nenhum dos dois estados é pendência.
  - INDISPONÍVEL: depois de 2 falhas de uma fonte de pesquisa (ou MCP
    desconectado), o orquestrador grava a etapa em $ID-indisponiveis.txt (uma
    por linha). O gate a mostra como [INDISPONIVEL] e não a cobra, desde que a
    OUTRA fonte de pesquisa esteja válida (as duas fora = trilho sem insumo,
    continua pendente).
  - DESVIO "embargos" na triagem: tudo depois da triagem vira [NAO_DEVIDA] (o
    bastão foi para o /pipeline-embargos). Desvio "prejudicado" segue o tronco
    inteiro, sem trilhos.
  - TRIAGEM: além das âncoras, o contrato C2 (exatamente um bloco ```json com
    rota/desvio/temas/fatos/justificativa) precisa ser válido.
  - ANÁLISE com fecho ESCALAR:/MOTIVO: -> exit 3 (válvula, máx 1 ciclo).
  - PUBLICAÇÃO: relatório, voto, ementa e acórdão integram o acórdão publicado e
    reprovam com markdown decorativo ou sinalizador interno ([VERIFICAR,
    [LACUNA, ESCALAR:/MOTIVO:) — mesma lista do verificar_minuta_limpa.py.
  - ACÓRDÃO sem resto de [FIM_EMENTA] e mais novo que ementa, relatório e voto
    (senão está desatualizado: re-rodar merge_voto.py).
  - COERÊNCIA: a ÚLTIMA linha casa ^VEREDITO: (COERENTE|DIVERGENTE — n itens)$,
    n bate com os blocos "DIVERGENCIA k" e cada bloco traz
    "RESPONSAVEL: VOTO|EMENTA". COERENTE -> exit 0; DIVERGENTE -> exit 4, com
    uma linha "RESPONSAVEL: <VOTO|EMENTA> (item k)" por divergência
    (regeneração dirigida). Mais nova que o acórdão, senão desatualizada.

Uso:
  python scripts/verificar_voto.py <workspace> [--id N]
      -> varredura: estado por etapa + "PENDENTES: ..." (o PLANO; exit 0)
  python scripts/verificar_voto.py <workspace> --etapas a,b
      -> varredura de um subconjunto (retomada de trilho; com --gate, fechamento)
  python scripts/verificar_voto.py <workspace> --etapa <nome>
      -> exit 0 válida | 1 ausente/inválida | 3 analise ESCALAR | 4 coerencia DIVERGENTE
  python scripts/verificar_voto.py <workspace> --rota
      -> contrato C2 da triagem: [DESVIO: embargos|prejudicado] na 1ª linha,
         ROTA:, JUSTIFICATIVA: (rota direta), TEMA:, FATO: (exit 0) | [ERRO] (exit 1)
  python scripts/verificar_voto.py <workspace> --gate
      -> exit 1 se qualquer etapa DEVIDA estiver pendente/inválida
Exit 2 = erro de uso (workspace inexistente, etapa desconhecida).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verificar_pipeline import _norm, inferir_id  # noqa: E402
from verificar_pipeline import verificar_etapa as _verificar_motor  # noqa: E402
from verificar_sentenca import detectar_escalar  # noqa: E402
from verificar_minuta_limpa import PROIBIDOS_PUBLICACAO  # noqa: E402

ETAPAS = {
    # etapa: (sufixo_do_arquivo, inicio, fim, contem[], minimo_chars)
    # Âncoras = <sinalizadores> reais dos agentes (staging da Onda B1).
    "linha-tempo": ("-linha-tempo.md", "# Linha do Tempo Recursal",
                    "É o que satisfaz extrair dos autos.",
                    ["PEÇAS-CHAVE", "Quem recorreu e de quê", "Ocorrências no tribunal"], 500),
    "relatorio": ("-relatorio.md", "RELATÓRIO", "É o relatório.", [], 500),
    "triagem": ("-triagem.md", "# Triagem Recursal", "Triagem concluída.",
                ["## QUESTÕES IDENTIFICADAS",
                 "## ADMISSIBILIDADE APARENTE E MATÉRIA DEVOLVIDA",
                 "## EVIDÊNCIAS", '"rota"'], 400),
    # --- condicionais (trilho de pesquisa) ---
    "pesquisa-tribunal": ("-pesquisa-tribunal.md", "# Pesquisa de Jurisprudência do Tribunal",
                          "Pesquisa concluída.",
                          ["Panorama do Tribunal de Origem", "Busca adversária",
                           "Fontes para Conferência Humana"], 300),
    # pesquisador-bnp REUSADO: mesmas âncoras da etapa "bnp" do verificar_pesquisa.py
    "pesquisa-bnp": ("-pesquisa-bnp.md", "# Pesquisa BNP", "Pesquisa BNP concluída.", [], 300),
    # --- condicional (trilho probático adversarial): só o PRODUTO final do trilho;
    # as etapas internas são do verificar_probatica.py (consolidado-adversarial) ---
    "probatica": ("-probatica-consolidado.md", "# SÍNTESE PROBATÓRIA CONSOLIDADA",
                  "Síntese probatória consolidada concluída.",
                  ["convergências", "contraprova", "consistência tese-réplica"], 500),
    # --- tronco ---
    "analise": ("-analise.md", "Vamos começar. Preciso pensar profundamente sobre esse recurso.",
                "Pronto.",
                ["Matriz Capítulo x Resultado", "Consectários Recursais",
                 "Observações Fora do Dispositivo"], 500),
    "voto": ("-voto.md", "VOTO", "É como voto.", ["Ante o exposto"], 500),
    "ementa": ("-ementa.md", "EMENTA", "[FIM_EMENTA]",
               ["I. CASO EM EXAME", "II. QUESTÃO EM DISCUSSÃO",
                "III. RAZÕES DE DECIDIR", "IV. DISPOSITIVO E TESE"], 300),
    "acordao": ("-acordao.md", "EMENTA", "É como voto.",
                ["RELATÓRIO", "É o relatório.", "Ante o exposto"], 1000),
    "coerencia": ("-coerencia.md", "# Conferência de Coerência do Acórdão", "VEREDITO:", [], 300),
}

ORDEM = list(ETAPAS)
POS_TRIAGEM = ORDEM[ORDEM.index("triagem") + 1:]
CONDICIONAIS = {"pesquisa-tribunal": "pesquisa", "pesquisa-bnp": "pesquisa",
                "probatica": "probatica"}
PAR_PESQUISA = {"pesquisa-tribunal": "pesquisa-bnp", "pesquisa-bnp": "pesquisa-tribunal"}
PUBLICACAO = ("relatorio", "voto", "ementa", "acordao")
DEPENDE_DE = {"acordao": ("ementa", "relatorio", "voto"), "coerencia": ("acordao",)}
DICA_DESATUALIZADO = {"acordao": "re-rodar merge_voto.py",
                      "coerencia": "redespachar a conferência de coerência"}
TRILHOS_VALIDOS = ("pesquisa", "probatica")
DESVIOS_VALIDOS = ("embargos", "prejudicado")
SUFIXO_INDISPONIVEIS = "-indisponiveis.txt"

RE_BLOCO_JSON = re.compile(r"```json\s*(.*?)```", re.DOTALL)
# Veredito: forma canônica do agente ("VEREDITO: DIVERGENTE — 2 itens"); aceita
# também "1 item" e traço curto, variações que não mudam o sentido.
RE_VEREDITO = re.compile(r"^VEREDITO: (COERENTE|DIVERGENTE [—–-] (\d+) (?:itens|item))$")
RE_LINHA_VEREDITO = re.compile(r"^[ \t]*VEREDITO:", re.MULTILINE)
# aplicados ao texto NORMALIZADO (sem acento, minúsculo)
RE_BLOCO_DIV = re.compile(r"^[ \t]*divergencia[ \t]+(\d+)[ \t]*$", re.MULTILINE)
RE_RESPONSAVEL = re.compile(r"^[ \t]*responsavel:[ \t]*(voto|ementa)\b", re.MULTILINE)


def _caminho(workspace, ident, etapa):
    return os.path.join(workspace, f"{ident}{ETAPAS[etapa][0]}")


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def _linha_unica(s):
    return " ".join(str(s).split())


# ----------------------------------------------------------------- rota (C2)

def validar_rota(dados):
    """Valida o contrato C2 da triagem recursal; devolve a violação ou None."""
    if not isinstance(dados, dict):
        return "bloco json não é um objeto"
    rota = dados.get("rota")
    if not isinstance(rota, list):
        return "campo 'rota' ausente ou não é lista"
    for t in rota:
        if t not in TRILHOS_VALIDOS:
            return f"trilho desconhecido na rota: {t!r} (aceitos: pesquisa, probatica)"
    temas = dados.get("temas_pesquisa")
    fatos = dados.get("fatos_probatorios")
    if temas is not None and not isinstance(temas, list):
        return "'temas_pesquisa' deve ser lista"
    if fatos is not None and not isinstance(fatos, list):
        return "'fatos_probatorios' deve ser lista"
    if "pesquisa" in rota and not [t for t in (temas or []) if str(t).strip()]:
        return "rota inclui 'pesquisa' mas temas_pesquisa está vazio"
    if "probatica" in rota and not [f for f in (fatos or []) if str(f).strip()]:
        return "rota inclui 'probatica' mas fatos_probatorios está vazio"
    desvio = dados.get("desvio")
    if desvio:
        if desvio not in DESVIOS_VALIDOS:
            return f"desvio desconhecido: {desvio!r} (aceitos: embargos, prejudicado)"
        if rota:
            return "desvio exige rota []"
    if not rota:
        j = dados.get("justificativa_rotina")
        if not isinstance(j, str) or not j.strip():
            return "rota direta ([]) exige justificativa_rotina não-vazia (certificação afirmativa)"
    return None


def ler_rota(workspace, ident):
    """(dados, None) com o C2 válido; (None, motivo) caso contrário."""
    caminho = _caminho(workspace, ident, "triagem")
    if not os.path.exists(caminho):
        return None, "triagem ausente"
    try:
        texto = _ler(caminho)
    except (OSError, UnicodeDecodeError) as e:
        return None, f"triagem ilegível: {e}"
    blocos = RE_BLOCO_JSON.findall(texto)
    if not blocos:
        return None, "triagem sem bloco ```json (contrato C2)"
    if len(blocos) > 1:
        return None, f"triagem com {len(blocos)} blocos ```json (o contrato C2 exige exatamente um)"
    try:
        dados = json.loads(blocos[0])
    except json.JSONDecodeError as e:
        return None, f"JSON malformado ({e})"
    erro = validar_rota(dados)
    return (None, erro) if erro else (dados, None)


def modo_rota(workspace, ident):
    dados, erro = ler_rota(workspace, ident)
    if erro:
        print(f"[ERRO] rota inválida: {erro}")
        return 1
    rota = list(dict.fromkeys(dados["rota"]))
    if dados.get("desvio"):
        print(f"DESVIO: {dados['desvio']}")
    print("ROTA: " + (" ".join(rota) if rota else "direta"))
    if not rota:
        print(f"JUSTIFICATIVA: {_linha_unica(dados['justificativa_rotina'])}")
    for tema in dados.get("temas_pesquisa") or []:
        if str(tema).strip():
            print(f"TEMA: {_linha_unica(tema)}")
    for fato in dados.get("fatos_probatorios") or []:
        if str(fato).strip():
            print(f"FATO: {_linha_unica(fato)}")
    return 0


# ----------------------------------------------------------------- coerência

def analisar_coerencia(texto):
    """(problemas, itens, veredito). itens = [(k, "VOTO"|"EMENTA"), ...]."""
    linhas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    ultima = linhas[-1] if linhas else ""
    m = RE_VEREDITO.match(ultima)
    if not m:
        return ([f"última linha não é veredito válido ({ultima[:60]!r}); esperado "
                 "'VEREDITO: COERENTE' ou 'VEREDITO: DIVERGENTE — <n> itens'"], [], None)
    problemas = []
    if len(RE_LINHA_VEREDITO.findall(texto)) > 1:
        problemas.append("mais de uma linha iniciada por 'VEREDITO:' (só a última pode)")
    n_texto = _norm(texto)
    blocos = list(RE_BLOCO_DIV.finditer(n_texto))
    itens = []
    for i, b in enumerate(blocos):
        fim = blocos[i + 1].start() if i + 1 < len(blocos) else len(n_texto)
        r = RE_RESPONSAVEL.search(n_texto, b.end(), fim)
        if r:
            itens.append((b.group(1), r.group(1).upper()))
        else:
            problemas.append(f"DIVERGENCIA {b.group(1)} sem 'RESPONSAVEL: VOTO|EMENTA'")
    if m.group(1) == "COERENTE":
        if blocos:
            problemas.append(f"veredito COERENTE com {len(blocos)} bloco(s) DIVERGENCIA")
        return problemas, itens, "COERENTE"
    n = int(m.group(2))
    if n == 0:
        problemas.append("DIVERGENTE com 0 itens (o veredito correto é COERENTE)")
    if n != len(blocos):
        problemas.append(f"veredito declara {n} item(ns) mas há {len(blocos)} bloco(s) DIVERGENCIA")
    return problemas, itens, "DIVERGENTE"


# ----------------------------------------------------------------- avaliação

def _desatualizado(workspace, ident, etapa):
    problemas = []
    proprio = os.path.getmtime(_caminho(workspace, ident, etapa))
    for dep in DEPENDE_DE.get(etapa, ()):
        p = _caminho(workspace, ident, dep)
        if os.path.exists(p) and os.path.getmtime(p) > proprio:
            problemas.append(f"desatualizado: mais antigo que {ident}{ETAPAS[dep][0]} "
                             f"({DICA_DESATUALIZADO[etapa]})")
    return problemas


def avaliar(workspace, ident, etapa):
    """Estado de UMA etapa: (status, dados).

    ("ausente", None) | ("invalida", [problemas]) | ("ok", None)
    | ("escalar", (trilhos, motivo))   — só analise (exit 3)
    | ("divergente", [(k, resp), ...]) — só coerencia (exit 4)
    """
    caminho = _caminho(workspace, ident, etapa)
    if not os.path.exists(caminho):
        return "ausente", None
    try:
        texto = _ler(caminho)
    except (OSError, UnicodeDecodeError) as e:
        return "invalida", [f"ilegível: {e}"]

    if etapa == "analise":
        esc = detectar_escalar(texto)
        if esc is not None:
            # ESCALAR dispensa o fecho "Pronto."; as demais checagens valem.
            sufixo, inicio, _fim, contem, minimo = ETAPAS["analise"]
            problemas = _verificar_motor(workspace, ident, "analise",
                                         {"analise": (sufixo, inicio, "", contem, minimo)}) or []
            trilhos, motivo = esc
            invalidos = [t for t in trilhos if t not in TRILHOS_VALIDOS]
            if invalidos:
                problemas.append(f"ESCALAR com trilho inválido: {invalidos[0]}")
            elif not trilhos:
                problemas.append("ESCALAR sem trilho declarado")
            return ("invalida", problemas) if problemas else ("escalar", (trilhos, motivo))

    problemas = _verificar_motor(workspace, ident, etapa, ETAPAS)
    if problemas is None:
        return "ausente", None
    if etapa == "triagem":
        _dados, erro = ler_rota(workspace, ident)
        if erro:
            problemas.append(f"rota inválida: {erro}")
    if etapa in PUBLICACAO:
        for rx, motivo in PROIBIDOS_PUBLICACAO:
            if rx.search(texto):
                problemas.append(f"contaminação de publicação: {motivo}")
    if etapa == "acordao" and "[fim_ementa]" in _norm(texto):
        problemas.append("resto do sinalizador [FIM_EMENTA] (merge_voto.py o remove)")
    if etapa in DEPENDE_DE:
        problemas += _desatualizado(workspace, ident, etapa)
    if etapa == "coerencia":
        extra, itens, veredito = analisar_coerencia(texto)
        problemas += extra
        if not problemas and veredito == "DIVERGENTE":
            return "divergente", itens
    return ("invalida", problemas) if problemas else ("ok", None)


def ler_indisponiveis(workspace, ident):
    caminho = os.path.join(workspace, f"{ident}{SUFIXO_INDISPONIVEIS}")
    if not os.path.exists(caminho):
        return set()
    try:
        return {ln.strip() for ln in _ler(caminho).splitlines() if ln.strip()}
    except (OSError, UnicodeDecodeError):
        return set()


def varredura(workspace, ident, alvo, gate=False):
    estados = {}

    def estado(etapa):
        if etapa not in estados:
            estados[etapa] = avaliar(workspace, ident, etapa)
        return estados[etapa]

    dados = None
    if estado("triagem")[0] == "ok":
        dados, _ = ler_rota(workspace, ident)
    desvio = (dados or {}).get("desvio") or None
    rota = (dados or {}).get("rota") or []
    escalados = []
    if desvio != "embargos" and estado("analise")[0] == "escalar":
        escalados = estado("analise")[1][0]
    indisponiveis = ler_indisponiveis(workspace, ident)

    pendentes, avaliadas, validas = [], 0, 0
    print(f"[INICIO] {ident} -> verificação de {len(alvo)} etapas (voto)")
    if desvio:
        print(f"[DESVIO] {desvio}")
    for etapa in alvo:
        if desvio == "embargos" and etapa in POS_TRIAGEM:
            print(f"[NAO_DEVIDA] {etapa} (desvio embargos)")
            continue
        if etapa in CONDICIONAIS:
            trilho = CONDICIONAIS[etapa]
            existe = os.path.exists(_caminho(workspace, ident, etapa))
            if dados is None and not existe:
                print(f"[AGUARDA_ROTA] {etapa}")
                continue
            if not (trilho in rota or trilho in escalados or existe):
                print(f"[NAO_DEVIDA] {etapa} (fora da rota)")
                continue
        status, info = estado(etapa)
        if (status != "ok" and etapa in indisponiveis and etapa in PAR_PESQUISA
                and estado(PAR_PESQUISA[etapa])[0] == "ok"):
            print(f"[INDISPONIVEL] {etapa}")
            continue
        avaliadas += 1
        if status == "ok":
            print(f"[OK] {etapa}")
            validas += 1
            continue
        pendentes.append(etapa)
        if status == "ausente":
            print(f"[AUSENTE] {etapa}")
        elif status == "escalar":
            print(f"[ESCALAR] {etapa}: {' '.join(info[0])}")
        elif status == "divergente":
            print(f"[DIVERGENTE] {etapa}: {len(info)} item(ns)")
        else:
            print(f"[INVALIDA] {etapa}: " + "; ".join(info))
    print("PENDENTES: " + (" ".join(pendentes) if pendentes else "(nenhuma)"))
    print(f"[FIM] {validas}/{avaliadas} válidas")
    return 1 if (gate and pendentes) else 0


def modo_etapa(workspace, ident, etapa):
    status, info = avaliar(workspace, ident, etapa)
    if status == "ausente":
        print(f"[AUSENTE] {etapa}")
        return 1
    if status == "invalida":
        print(f"[INVALIDA] {etapa}: " + "; ".join(info))
        return 1
    if status == "escalar":
        trilhos, motivo = info
        print(f"[ESCALAR] {etapa}: {' '.join(trilhos)} — {motivo}")
        return 3
    if status == "divergente":
        print(f"[DIVERGENTE] {etapa}: {len(info)} item(ns)")
        for k, resp in info:
            print(f"RESPONSAVEL: {resp} (item {k})")
        return 4
    print(f"[OK] {etapa}")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Gate determinístico do pipeline de voto (v3.0).")
    ap.add_argument("workspace")
    ap.add_argument("--id", "--numero", dest="ident",
                    help="prefixo dos arquivos (inferido do nome da pasta se omitido)")
    ap.add_argument("--etapa", choices=sorted(ETAPAS),
                    help="valida só esta etapa (0 ok, 1 inválida, 3 ESCALAR, 4 DIVERGENTE)")
    ap.add_argument("--etapas", help="subconjunto separado por vírgula (retomada de trilho)")
    ap.add_argument("--rota", action="store_true",
                    help="imprime DESVIO:/ROTA:/JUSTIFICATIVA:/TEMA:/FATO: do contrato C2")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 se qualquer etapa devida estiver pendente/inválida")
    a = ap.parse_args()

    if not os.path.isdir(a.workspace):
        print(f"[ERRO] workspace inexistente: {a.workspace}")
        sys.exit(2)
    ident = a.ident or inferir_id(a.workspace)
    if not ident:
        print("[ERRO] identificador não inferível do nome da pasta — passe --id")
        sys.exit(2)

    if a.rota:
        sys.exit(modo_rota(a.workspace, ident))
    if a.etapa:
        sys.exit(modo_etapa(a.workspace, ident, a.etapa))
    if a.etapas:
        alvo = [e.strip() for e in a.etapas.split(",") if e.strip()]
        desconhecidas = [e for e in alvo if e not in ETAPAS]
        if desconhecidas:
            print(f"[ERRO] etapa(s) desconhecida(s): {', '.join(desconhecidas)}")
            sys.exit(2)
    else:
        alvo = list(ETAPAS)
    sys.exit(varredura(a.workspace, ident, alvo, gate=a.gate))


if __name__ == "__main__":
    main()
