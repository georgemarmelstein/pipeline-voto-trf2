#!/usr/bin/env python3
"""verificar_proveniencia.py - Gate Camada B: fontes.json ⊆ base oficial.

Para cada fonte do $NUMERO-fontes.json, recupera o texto oficial pela IDENTIDADE
(adaptadores por dialeto) e casa o trecho_verbatim LOCALMENTE. Estados:
CONFIRMADA | NAO_ENCONTRADA | BASE_INDISPONIVEL | SEM_ADAPTADOR.

Políticas (spec 24/07/2026):
  - NAO_ENCONTRADA bloqueia SEMPRE (a cadeia de custódia mentiu);
  - citável em BASE_INDISPONIVEL/SEM_ADAPTADOR bloqueia a assinatura automática
    (decisão humana na prancha, que exibe hash/data da captura);
  - não-citável indisponível é aviso.

O gate roda duas vezes no pipeline: cedo (logo após o merge, ANTES da análise
marcar os citáveis — ausência de <id>-citaveis.json é legítima e vira só
[AVISO]) e no final (pré-assinatura, onde a ausência precisa BLOQUEAR — use
--exigir-citaveis). A política de citáveis NUNCA é desligada em silêncio.

Cache em <workspace>/custodia/proveniencia-cache.json (chave por conteúdo);
--offline usa só o cache (para retomadas e testes). Retry: 2 tentativas.

Uso:
  python scripts/verificar_proveniencia.py <workspace> [--id N] [--fontes SUFIXO]
      [--so-citaveis] [--offline] [--exigir-citaveis] [--max-fragmentos 3]
"""
import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proveniencia_core import (CONFIRMADA, NAO_ENCONTRADA, BASE_INDISPONIVEL,
                               SEM_ADAPTADOR, RE_CNJ, casar_trecho, norm)
from proveniencia_adapters import (ADAPTADORES, BaseIndisponivel,
                                   obter_textos_oficiais)

TENTATIVAS = 2
PAUSA_S = 3


def chave_fonte(fonte):
    bruto = "|".join([fonte.get("origem_mcp", ""), fonte.get("referencia", ""),
                      norm(fonte.get("trecho_verbatim", ""))])
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:16]


def obter_padrao(fonte, max_fragmentos=3):
    """Indireção para permitir fake nos testes."""
    return obter_textos_oficiais(fonte, max_fragmentos)


def processar_fontes(fontes, refs_citaveis, obter, cache, max_fragmentos=3,
                     offline=False):
    """refs_citaveis: set de referências NORMALIZADAS (norm()) citáveis — a
    própria referência de cada entrada de citaveis.json mais suas
    referencias_equivalentes. NUNCA ids: o merge_fontes.py reatribui ids a
    cada rodada, então id não é chave de casamento estável (spec 24/07/2026)."""
    resultados = []
    for fonte in fontes:
        chave = chave_fonte(fonte)
        origem = fonte.get("origem_mcp", "?")
        if chave in cache:
            entry = cache[chave]
            estado = entry["estado"]
            detalhe = "cache: " + entry.get("detalhe", "")
        elif offline:
            estado, detalhe = BASE_INDISPONIVEL, "sem cache em modo offline"
        elif origem not in ADAPTADORES:
            # SEM_ADAPTADOR é decidido por MEMBERSHIP, antes de chamar `obter`
            # — nunca por exceção. Uma fonte malformada (ex.: sem
            # trecho_verbatim) não é "sem adaptador": é bug do chamador e deve
            # estourar alto (KeyError), não ser disfarçada de estado de infra.
            estado, detalhe = SEM_ADAPTADOR, origem
        else:
            estado, detalhe = None, ""
            for tentativa in range(TENTATIVAS):
                try:
                    textos = obter(fonte, max_fragmentos)
                    casou, frag = casar_trecho(fonte["trecho_verbatim"], textos)
                    estado = CONFIRMADA if casou else NAO_ENCONTRADA
                    detalhe = "" if casou else f"fragmento sem eco: {frag[:80]}..."
                    break
                except BaseIndisponivel as e:
                    estado, detalhe = BASE_INDISPONIVEL, str(e)[:120]
                    if tentativa < TENTATIVAS - 1:
                        time.sleep(PAUSA_S)
            if estado in (CONFIRMADA, NAO_ENCONTRADA):
                cache[chave] = {"estado": estado,
                                "data": time.strftime("%Y-%m-%d"),
                                "detalhe": detalhe}
        resultados.append({"id": fonte.get("id", "?"),
                           "referencia": fonte.get("referencia", "?"),
                           "estado": estado, "detalhe": detalhe,
                           "citavel": norm(fonte.get("referencia", "")) in refs_citaveis})
    return resultados


def citaveis_nao_resolvidos(entradas, resultados):
    """Para cada entrada de citaveis.json (fontes[]), verifica se existe algum
    resultado (de processar_fontes) cuja referência normalizada bate com a
    referência da entrada OU com alguma de suas referencias_equivalentes E
    cujo estado é CONFIRMADA. Retorna a `referencia` (texto original) de cada
    entrada NÃO resolvida.

    Um citável sem fonte CONFIRMADA correspondente é referência alucinada ou
    fonte rejeitada na origem/merge — a prancha (não-bloqueante) já mostra
    AUSENTE, mas o gate final precisa bloquear a assinatura (spec 24/07/2026)."""
    nao_resolvidos = []
    for entrada in entradas:
        ref_original = entrada.get("referencia", "")
        refs = {norm(ref_original)}
        for eq in entrada.get("referencias_equivalentes", []) or []:
            if eq:
                refs.add(norm(eq))
        resolvido = any(norm(r.get("referencia", "")) in refs
                        and r.get("estado") == CONFIRMADA
                        for r in resultados)
        if not resolvido:
            nao_resolvidos.append(ref_original)
    return nao_resolvidos


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Gate de proveniência (Camada B).")
    ap.add_argument("workspace")
    ap.add_argument("--id", dest="ident")
    ap.add_argument("--fontes", dest="fontes_arg", default="-fontes.json")
    ap.add_argument("--so-citaveis", action="store_true",
                    help="verifica apenas as fontes citáveis")
    ap.add_argument("--offline", action="store_true",
                    help="usa só o cache (retomada/testes)")
    ap.add_argument("--exigir-citaveis", action="store_true",
                    help="bloqueia (exit 1) se <id>-citaveis.json estiver "
                         "ausente — gate final, pré-assinatura")
    ap.add_argument("--max-fragmentos", type=int, default=3)
    a = ap.parse_args()

    if not os.path.isdir(a.workspace):
        print(f"[ERRO] workspace inexistente: {a.workspace}")
        sys.exit(2)
    base = os.path.basename(os.path.abspath(a.workspace))
    m = RE_CNJ.search(base)
    ident = a.ident or (m.group(0) if m else base)

    caminho_fontes = os.path.join(a.workspace, ident + a.fontes_arg)
    if not os.path.exists(caminho_fontes):
        print(f"[ERRO] fontes inexistente: {caminho_fontes}")
        sys.exit(2)
    with open(caminho_fontes, encoding="utf-8") as f:
        fontes = json.load(f).get("fontes", [])

    refs_citaveis = set()
    entradas_cit = []
    caminho_cit = os.path.join(a.workspace, ident + "-citaveis.json")
    if os.path.exists(caminho_cit):
        with open(caminho_cit, encoding="utf-8") as f:
            entradas_cit = json.load(f).get("fontes", [])
        for e in entradas_cit:
            ref = e.get("referencia", "")
            if ref:
                refs_citaveis.add(norm(ref))
            for eq in e.get("referencias_equivalentes", []) or []:
                if eq:
                    refs_citaveis.add(norm(eq))
    elif a.exigir_citaveis:
        print("[ERRO] citaveis.json ausente (--exigir-citaveis)")
        sys.exit(1)
    else:
        print(f"[AVISO] sem {ident}-citaveis.json — política de citáveis NÃO "
              f"aplicada (re-rodar após a marcação da análise)")
    if a.so_citaveis:
        fontes = [f for f in fontes if norm(f.get("referencia", "")) in refs_citaveis]

    pasta_custodia = os.path.join(a.workspace, "custodia")
    os.makedirs(pasta_custodia, exist_ok=True)
    caminho_cache = os.path.join(pasta_custodia, "proveniencia-cache.json")
    cache = {}
    if os.path.exists(caminho_cache):
        with open(caminho_cache, encoding="utf-8") as f:
            cache = json.load(f)

    print(f"[INICIO] {len(fontes)} fonte(s) -> gate de proveniência"
          + (" (offline)" if a.offline else ""))
    resultados = processar_fontes(fontes, refs_citaveis, obter_padrao, cache,
                                  a.max_fragmentos, a.offline)
    with open(caminho_cache, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    bloqueios = avisos = 0
    for r in resultados:
        rotulo = f"{r['id']} {r['referencia']}" + (" [citável]" if r["citavel"] else "")
        if r["estado"] == CONFIRMADA:
            marca = " (cache)" if r["detalhe"].startswith("cache:") else ""
            print(f"[OK] {rotulo}: CONFIRMADA{marca}")
        elif r["estado"] == NAO_ENCONTRADA:
            print(f"[ERRO] {rotulo}: NAO_ENCONTRADA — {r['detalhe']}")
            bloqueios += 1
        elif r["citavel"]:
            print(f"[ERRO] {rotulo}: {r['estado']} — decisão humana na prancha "
                  f"({r['detalhe']})")
            bloqueios += 1
        else:
            print(f"[AVISO] {rotulo}: {r['estado']} ({r['detalhe']})")
            avisos += 1
    if a.exigir_citaveis:
        # Resolução vê TODOS os resultados processados (fontes já veio
        # filtrada por --so-citaveis se a flag estiver ligada, mas um
        # citável só casa com fonte citável por definição — filtrar ou não
        # dá o mesmo resultado; ver nota no módulo).
        for ref in citaveis_nao_resolvidos(entradas_cit, resultados):
            print(f"[ERRO] citável sem fonte CONFIRMADA: {ref} — bloqueia a assinatura")
            bloqueios += 1
    confirmadas = sum(1 for r in resultados if r["estado"] == CONFIRMADA)
    print(f"[FIM] {confirmadas}/{len(resultados)} confirmadas, "
          f"{bloqueios} bloqueio(s), {avisos} aviso(s)")
    sys.exit(1 if bloqueios else 0)


if __name__ == "__main__":
    main()
