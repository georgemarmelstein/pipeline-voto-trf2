"""
Modulo de Classificacao Qualitativa de Processos

Funcoes auxiliares para o sistema de classificacao por temas.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional


def carregar_meta(pasta_processo: Path) -> Optional[dict]:
    """
    Carrega metadados de um processo se existirem.

    Args:
        pasta_processo: Pasta do processo no Kanban

    Returns:
        Dict com metadados ou None se nao existir
    """
    for arquivo in pasta_processo.glob("*-meta.json"):
        try:
            return json.loads(arquivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return None


def carregar_todos_metas(base_path: Path, tipo: str = "decisao") -> list[dict]:
    """
    Carrega metadados de todos os processos de um tipo.

    Args:
        base_path: Caminho base do Kanban
        tipo: "sentenca" ou "decisao"

    Returns:
        Lista de dicts com metadados
    """
    metas = []
    tipo_path = base_path / tipo

    if not tipo_path.exists():
        return metas

    # Percorre todas as colunas do Kanban
    for coluna in tipo_path.iterdir():
        if not coluna.is_dir():
            continue

        # Percorre processos na coluna
        for processo_dir in coluna.iterdir():
            if not processo_dir.is_dir():
                continue

            meta = carregar_meta(processo_dir)
            if meta:
                # Adiciona informacao da coluna atual
                meta["_coluna"] = coluna.name
                meta["_caminho"] = str(processo_dir)
                metas.append(meta)

    return metas


def extrair_tema(meta: dict) -> str:
    """
    Extrai o tema do processo.
    """
    tema = meta.get("tema", "")

    if not tema:
        classificacao = meta.get("classificacao", {})
        if isinstance(classificacao, dict):
            tema = classificacao.get("cluster", "nao-classificado")
        else:
            tema = "nao-classificado"

    return tema


def extrair_tema_nome(meta: dict) -> str:
    """
    Extrai o nome legivel do tema.
    """
    nome = meta.get("tema_nome", "")

    if not nome:
        classificacao = meta.get("classificacao", {})
        if isinstance(classificacao, dict):
            nome = classificacao.get("cluster_nome", "Nao Classificado")
        else:
            nome = "Nao Classificado"

    return nome


def extrair_urgencia(meta: dict) -> str:
    """Extrai urgencia."""
    urgencia = meta.get("analise", {}).get("urgencia", "")

    if not urgencia:
        urgencia = meta.get("analise_qualitativa", {}).get("urgencia", "normal")

    return urgencia


def extrair_complexidade(meta: dict) -> str:
    """Extrai complexidade."""
    complexidade = meta.get("analise", {}).get("complexidade", "")

    if not complexidade:
        complexidade = meta.get("analise_qualitativa", {}).get("complexidade", "media")

    return complexidade


def extrair_dias_concluso(meta: dict) -> int:
    """Extrai dias concluso."""
    return meta.get("datas", {}).get("dias_concluso", 0)


def gerar_dashboard(base_path: Path, tipo: str = "decisao") -> dict:
    """
    Gera estatisticas do dashboard para visualizacao sistemica.

    Args:
        base_path: Caminho base do Kanban
        tipo: "sentenca" ou "decisao"

    Returns:
        Dict com estatisticas agregadas por TEMA
    """
    metas = carregar_todos_metas(base_path, tipo)

    if not metas:
        return {
            "total": 0,
            "por_tema": {},
            "por_urgencia": {},
            "por_complexidade": {},
            "prioridades_legais": {},
            "alertas_cnj": {},
            "por_coluna": {},
            "teses": []
        }

    # Contadores
    por_tema = {}
    por_urgencia = {"critica": 0, "alta": 0, "normal": 0}
    por_complexidade = {"baixa": 0, "media": 0, "alta": 0}
    prioridades = {"idoso": 0, "deficiente": 0, "doenca_grave": 0, "crianca_adolescente": 0, "reu_preso": 0}
    alertas_cnj = {"mais_100_dias": 0, "mais_60_dias": 0, "mais_30_dias": 0}
    por_coluna = {}
    teses_encontradas = {}

    for meta in metas:
        # Tema
        tema = extrair_tema(meta)
        tema_nome = extrair_tema_nome(meta)

        if tema not in por_tema:
            por_tema[tema] = {"count": 0, "nome": tema_nome, "processos": []}
        por_tema[tema]["count"] += 1
        por_tema[tema]["processos"].append(meta.get("numero_processo", ""))

        # Urgencia
        urgencia = extrair_urgencia(meta)
        por_urgencia[urgencia] = por_urgencia.get(urgencia, 0) + 1

        # Complexidade
        complexidade = extrair_complexidade(meta)
        por_complexidade[complexidade] = por_complexidade.get(complexidade, 0) + 1

        # Prioridades legais
        for prio, valor in meta.get("prioridade_legal", {}).items():
            if valor:
                prioridades[prio] = prioridades.get(prio, 0) + 1

        # Alertas CNJ (dias concluso)
        dias = extrair_dias_concluso(meta)
        if dias > 100:
            alertas_cnj["mais_100_dias"] += 1
        elif dias > 60:
            alertas_cnj["mais_60_dias"] += 1
        elif dias > 30:
            alertas_cnj["mais_30_dias"] += 1

        # Por coluna
        coluna = meta.get("_coluna", "desconhecido")
        por_coluna[coluna] = por_coluna.get(coluna, 0) + 1

        # Teses relacionadas
        for tese in meta.get("teses_relacionadas", []):
            if isinstance(tese, str):
                continue
            chave = f"{tese.get('tribunal', '')}-{tese.get('numero', '')}"
            if chave not in teses_encontradas:
                teses_encontradas[chave] = {
                    "numero": tese.get("numero", ""),
                    "tribunal": tese.get("tribunal", ""),
                    "descricao": tese.get("descricao", ""),
                    "status": tese.get("status", ""),
                    "processos": []
                }
            teses_encontradas[chave]["processos"].append(meta.get("numero_processo", ""))

    # Ordena temas por quantidade
    por_tema_ordenado = dict(sorted(por_tema.items(), key=lambda x: -x[1]["count"]))

    return {
        "total": len(metas),
        "por_tema": por_tema_ordenado,
        "por_urgencia": por_urgencia,
        "por_complexidade": por_complexidade,
        "prioridades_legais": prioridades,
        "alertas_cnj": alertas_cnj,
        "por_coluna": por_coluna,
        "teses": list(teses_encontradas.values()),
        "gerado_em": datetime.now().isoformat()
    }


def gerar_pauta(base_path: Path, tipo: str = "decisao", max_itens: int = 20) -> dict:
    """
    Gera pauta operacional priorizada para o dia.

    Args:
        base_path: Caminho base do Kanban
        tipo: "sentenca" ou "decisao"
        max_itens: Maximo de itens na pauta

    Returns:
        Dict com pauta estruturada por tema
    """
    metas = carregar_todos_metas(base_path, tipo)

    # Filtra apenas processos a analisar
    por_analisar = [
        m for m in metas
        if "01-por-analisar" in m.get("_coluna", "") and m.get("numero_processo")
    ]

    # Separa por urgencia
    criticos = []
    urgentes = []
    normais = []

    for meta in por_analisar:
        urgencia = extrair_urgencia(meta)
        if urgencia == "critica":
            criticos.append(meta)
        elif urgencia == "alta":
            urgentes.append(meta)
        else:
            normais.append(meta)

    # Ordena normais por dias concluso (mais antigo primeiro)
    normais.sort(key=lambda x: extrair_dias_concluso(x), reverse=True)

    # Identifica foco sugerido (tema mais frequente)
    temas = {}
    for meta in por_analisar:
        tema = extrair_tema(meta)
        if tema:
            if tema not in temas:
                temas[tema] = {"count": 0, "nome": extrair_tema_nome(meta), "processos": []}
            temas[tema]["count"] += 1
            temas[tema]["processos"].append(meta.get("numero_processo", ""))

    foco_sugerido = None
    if temas:
        foco_tema = max(temas, key=lambda x: temas[x]["count"])
        if temas[foco_tema]["count"] >= 2:
            foco_sugerido = {
                "tema": foco_tema,
                "tema_nome": temas[foco_tema]["nome"],
                "quantidade": temas[foco_tema]["count"],
                "processos": temas[foco_tema]["processos"][:10]
            }

    # Agrupa normais por tema
    por_tema = {}
    for meta in normais:
        tema = extrair_tema(meta)
        if tema not in por_tema:
            por_tema[tema] = []
        por_tema[tema].append(meta)

    # Monta pauta
    pauta = {
        "data": date.today().isoformat(),
        "tipo": tipo,
        "total_por_analisar": len(por_analisar),
        "criticos": [
            {
                "numero": m["numero_processo"],
                "tema": extrair_tema(m),
                "tema_nome": extrair_tema_nome(m),
                "motivo": m.get("analise", {}).get("motivo_urgencia", ""),
                "dias_concluso": extrair_dias_concluso(m)
            }
            for m in criticos[:5]
        ],
        "urgentes": [
            {
                "numero": m["numero_processo"],
                "tema": extrair_tema(m),
                "tema_nome": extrair_tema_nome(m),
                "motivo": m.get("analise", {}).get("motivo_urgencia", ""),
                "dias_concluso": extrair_dias_concluso(m)
            }
            for m in urgentes[:5]
        ],
        "foco_sugerido": foco_sugerido,
        "por_tema": {
            tema: [
                {
                    "numero": m["numero_processo"],
                    "dias_concluso": extrair_dias_concluso(m),
                    "complexidade": extrair_complexidade(m)
                }
                for m in processos[:5]
            ]
            for tema, processos in sorted(por_tema.items(), key=lambda x: -len(x[1]))
        },
        "conformidade_cnj": [
            {
                "numero": m["numero_processo"],
                "tema": extrair_tema(m),
                "dias_concluso": extrair_dias_concluso(m)
            }
            for m in normais if extrair_dias_concluso(m) > 60
        ][:5],
        "gerado_em": datetime.now().isoformat()
    }

    return pauta


def filtrar_processos(
    base_path: Path,
    tipo: str = "decisao",
    tema: Optional[str] = None,
    urgencia: Optional[str] = None,
    complexidade: Optional[str] = None,
    coluna: Optional[str] = None,
    dias_concluso_min: Optional[int] = None,
    prioridade_legal: Optional[str] = None
) -> list[dict]:
    """
    Filtra processos por multiplos criterios (Modo Foco).

    Args:
        base_path: Caminho base do Kanban
        tipo: "sentenca" ou "decisao"
        tema: Filtrar por tema especifico
        urgencia: Filtrar por urgencia (critica, alta, normal)
        complexidade: Filtrar por complexidade (baixa, media, alta)
        coluna: Filtrar por coluna do Kanban
        dias_concluso_min: Minimo de dias concluso
        prioridade_legal: Filtrar por prioridade (idoso, deficiente, etc.)

    Returns:
        Lista de processos filtrados
    """
    metas = carregar_todos_metas(base_path, tipo)

    resultado = []

    for meta in metas:
        # Filtro por tema
        if tema:
            if extrair_tema(meta) != tema:
                continue

        # Filtro por urgencia
        if urgencia:
            if extrair_urgencia(meta) != urgencia:
                continue

        # Filtro por complexidade
        if complexidade:
            if extrair_complexidade(meta) != complexidade:
                continue

        # Filtro por coluna
        if coluna:
            if coluna not in meta.get("_coluna", ""):
                continue

        # Filtro por dias concluso
        if dias_concluso_min is not None:
            if extrair_dias_concluso(meta) < dias_concluso_min:
                continue

        # Filtro por prioridade legal
        if prioridade_legal:
            if not meta.get("prioridade_legal", {}).get(prioridade_legal, False):
                continue

        resultado.append(meta)

    return resultado
