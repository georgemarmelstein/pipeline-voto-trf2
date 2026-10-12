from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import shutil
import re

from app import config
from app.config import TipoProcesso

# Bloco JSON cercado (```json ... ```) do contrato C2 da triagem v3.1
RE_BLOCO_JSON = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def extrair_meta_v31(proc_dir: Path, numero: str) -> Dict[str, Any]:
    """
    Detecta metadados leves do pipeline v3.1 no workspace (sem parsing pesado).

    - "rota": lista do contrato C2 (primeiro bloco ```json da triagem),
      ex.: ["pesquisa", "probatica"] ou [] (rota direta)
    - "tem_fontes": True se existe <numero>-fontes.json

    Qualquer falha → campo ausente (nunca derruba a listagem).
    """
    meta: Dict[str, Any] = {}
    try:
        triagem = proc_dir / f"{numero}-triagem.md"
        if triagem.is_file():
            match = RE_BLOCO_JSON.search(triagem.read_text(encoding="utf-8"))
            if match:
                contrato = json.loads(match.group(1))
                rota = contrato.get("rota")
                if isinstance(rota, list):
                    meta["rota"] = rota
        if (proc_dir / f"{numero}-fontes.json").is_file():
            meta["tem_fontes"] = True
    except Exception:
        pass  # metadado é opcional: nunca quebrar a listagem
    return meta


def get_pasta_tipo(tipo: TipoProcesso) -> Path:
    """Retorna o caminho base para um tipo de processo."""
    return config.BASE_PATH / tipo.value


def get_pasta_estado(tipo: TipoProcesso, estado: str) -> Path:
    """Retorna o caminho completo para um estado de um tipo de processo."""
    return get_pasta_tipo(tipo) / config.ESTADOS[estado]


def listar_processos(tipo: Optional[TipoProcesso] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Lista todos os processos organizados por estado.

    Args:
        tipo: Tipo de processo (sentenca/decisao). Se None, retorna de ambos.

    Returns:
        Dict com chave = estado, valor = lista de processos
    """
    resultado = {}

    # Se tipo especificado, listar apenas desse tipo
    tipos = [tipo] if tipo else config.TIPOS_PROCESSO

    for estado_key in config.ESTADOS.keys():
        processos = []

        for t in tipos:
            pasta_estado = get_pasta_estado(t, estado_key)

            if pasta_estado.exists():
                for proc_dir in pasta_estado.iterdir():
                    if proc_dir.is_dir():
                        item = {
                            "numero": proc_dir.name,
                            "estado": estado_key,
                            "tipo": t.value,
                            "caminho": str(proc_dir),
                        }
                        # Selo de rota v3.1 (triagem + fontes), barato e tolerante
                        item.update(extrair_meta_v31(proc_dir, proc_dir.name))
                        processos.append(item)

        # Ordenar por numero do processo
        processos.sort(key=lambda p: p["numero"])
        resultado[estado_key] = processos

    return resultado


def contar_processos_por_tipo() -> Dict[str, int]:
    """
    Conta processos por tipo (para badges das abas).

    Returns:
        Dict com chave = tipo, valor = contagem total
    """
    contagem = {}

    for tipo in config.TIPOS_PROCESSO:
        total = 0
        for estado_key in config.ORDEM_ESTADOS:  # Nao conta arquivados
            pasta_estado = get_pasta_estado(tipo, estado_key)
            if pasta_estado.exists():
                total += sum(1 for d in pasta_estado.iterdir() if d.is_dir())
        contagem[tipo.value] = total

    return contagem


def mover_processo(
    numero: str,
    estado_origem: str,
    estado_destino: str,
    tipo: TipoProcesso = TipoProcesso.SENTENCA,
    sobrescrever: bool = False
) -> Dict[str, Any]:
    """
    Move um processo de um estado para outro.

    Args:
        numero: Numero do processo (nome da pasta)
        estado_origem: Estado atual (key, ex: "por-analisar")
        estado_destino: Novo estado (key, ex: "analisando")
        tipo: Tipo de processo (sentenca/decisao)
        sobrescrever: Se True, mescla arquivos quando destino ja existe
                      (novos sobrescrevem antigos, unicos sao mantidos)

    Returns:
        Dict com sucesso=True/False e mensagem de erro se houver
    """
    try:
        pasta_origem = get_pasta_estado(tipo, estado_origem) / numero
        pasta_destino = get_pasta_estado(tipo, estado_destino) / numero

        if not pasta_origem.exists():
            return {"sucesso": False, "erro": f"Processo nao encontrado: {numero}"}

        if pasta_destino.exists():
            if not sobrescrever:
                return {
                    "sucesso": False,
                    "erro": f"Ja existe processo no destino: {numero}",
                    "conflito": True
                }

            # Modo sobrescrita: mesclar arquivos
            # Copiar todos os arquivos da origem para destino (sobrescrevendo)
            arquivos_mesclados = []
            arquivos_mantidos = []

            for item in pasta_origem.rglob("*"):
                if item.is_file():
                    # Calcular caminho relativo e destino
                    rel_path = item.relative_to(pasta_origem)
                    destino_arquivo = pasta_destino / rel_path

                    # Criar subpastas se necessario
                    destino_arquivo.parent.mkdir(parents=True, exist_ok=True)

                    if destino_arquivo.exists():
                        arquivos_mesclados.append(str(rel_path))
                    else:
                        arquivos_mantidos.append(str(rel_path))

                    # Copiar (sobrescreve se existir)
                    shutil.copy2(str(item), str(destino_arquivo))

            # Remover pasta de origem apos copia bem-sucedida
            shutil.rmtree(str(pasta_origem))

            return {
                "sucesso": True,
                "novo_caminho": str(pasta_destino),
                "mesclado": True,
                "arquivos_sobrescritos": arquivos_mesclados,
                "arquivos_novos": arquivos_mantidos
            }

        # Criar pasta de destino se nao existir (ex: 05-arquivados)
        pasta_destino.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(pasta_origem), str(pasta_destino))

        return {"sucesso": True, "novo_caminho": str(pasta_destino)}

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


# Mapeamento de artefatos curados para exibicao no preview
ARTEFATOS_CURADOS = {
    "linha-tempo": (
        ["{numero}-linha-tempo.md"],
        "Linha do Tempo",
        -2,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
    ),
    "relatorio": (
        ["{numero}-relatorio.md", "relatorio.md", "relatorio-completo.md"],
        "Relatorio",
        -1,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>'
    ),
    "triagem": (
        ["{numero}-triagem.md"],
        "Triagem",
        -0.5,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>'
    ),
    "analise": (
        ["{numero}-analise.md"],
        "Analise",
        0,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'
    ),
    "fundamentacao": (
        ["{numero}-fundamentacao.md", "fundamentacao.md"],
        "Fundamentacao",
        1,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
    ),
    "precedentes": (
        ["{numero}-precedentes-consolidado.md", "{numero}-precedentes.md"],
        "Precedentes",
        2,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/><path d="M11 8v6"/><path d="M8 11h6"/></svg>'
    ),
    "inventario": (
        ["{numero}-inventario.md"],
        "Inventario",
        2.5,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/></svg>'
    ),
    "probatica_pearl": (
        ["{numero}-pearl.md"],
        "Pearl",
        3,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>'
    ),
    "probatica_haack": (
        ["{numero}-haack.md"],
        "Haack",
        4,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>'
    ),
    "probatica_fbd": (
        ["{numero}-probatica-fbd.md"],
        "FBD",
        4.5,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18"/><path d="M5 7h14"/><path d="M5 7l-2 5a3 3 0 0 0 6 0l-2-5"/><path d="M19 7l-2 5a3 3 0 0 0 6 0l-2-5"/></svg>'
    ),
    "probatica": (
        ["{numero}-probatica.md"],
        "Probatica",
        5,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>'
    ),
    "probatica_consolidado": (
        ["{numero}-probatica-consolidado.md"],
        "Síntese Probática",
        5.5,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>'
    ),
    "embargos_analise": (
        ["{numero}-embargos-analise.md"],
        "Emb. Analise",
        6,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18v-6"/><path d="M9 15l3 3 3-3"/></svg>'
    ),
    "revisao": (
        ["{numero}-revisao.md"],
        "Revisao",
        7,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>'
    ),
    # Agent Teams - Pesquisas
    "pesquisa_bnp": (
        ["{numero}-pesquisa-bnp.md"],
        "BNP",
        10,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    ),
    "pesquisa_cjf": (
        ["{numero}-pesquisa-cjf.md"],
        "CJF",
        11,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    ),
    "pesquisa_julia": (
        ["{numero}-pesquisa-julia.md"],
        "JULIA",
        12,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    ),
    "pesquisa_stj": (
        ["{numero}-pesquisa-stj.md"],
        "STJ",
        13,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    ),
    "pesquisa_tnu": (
        ["{numero}-pesquisa-tnu.md"],
        "TNU",
        14,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    ),
    # Agent Teams - Verificacoes
    "verificacao_honorarios": (
        ["{numero}-verificacao-honorarios.md"],
        "Honorarios",
        20,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>'
    ),
    "verificacao_calculos": (
        ["{numero}-verificacao-calculos.md"],
        "Calculos",
        21,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="12" y2="14"/><line x1="8" y1="18" x2="12" y2="18"/></svg>'
    ),
    "verificacao_remessa": (
        ["{numero}-verificacao-remessa.md"],
        "Remessa",
        22,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19V5M5 12l7-7 7 7"/></svg>'
    ),
    "verificacao_fontes": (
        ["{numero}-verificacao-fontes.md"],
        "Fontes",
        23,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M9 10l2 2 4-4"/></svg>'
    ),
    "embargabilidade": (
        ["{numero}-analise-embargabilidade.md"],
        "Embargabilidade",
        24,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    ),
    # Pipeline-voto (acórdão de 2º grau)
    "pesquisa_tribunal": (
        ["{numero}-pesquisa-tribunal.md"],
        "TRF",
        9.5,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    ),
    "coerencia": (
        ["{numero}-coerencia.md"],
        "Coerência",
        25,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>'
    ),
    "vereditos_parafrase": (
        ["{numero}-vereditos-parafrase.md"],
        "Paráfrase",
        26,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>'
    ),
    "conferencia_fontes": (
        ["{numero}-conferencia-fontes.md"],
        "Prancha",
        27,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>'
    ),
}

# Mapeamento de minutas curadas para exibicao no painel de minutas
MINUTAS_CURADAS = {
    "acordao": (
        ["{numero}-acordao.md"],
        "Acórdão",
        0,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
    ),
    "sentenca": (
        ["{numero}-sentenca.md", "{numero}-minuta.md", "{numero}-minuta-completa.md"],
        "Sentenca",
        1,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
    ),
    "robustecida": (
        ["{numero}-minuta-robustecida.md"],
        "Robustecida",
        2,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>'
    ),
    "embargos_minuta": (
        ["{numero}-embargos-minuta.md"],
        "Embargos",
        2.5,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18v-6"/><path d="M9 15l3 3 3-3"/></svg>'
    ),
    "despacho": (
        ["{numero}-despacho.md"],
        "Despacho",
        3,
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 15h6"/><path d="M12 18V12"/></svg>'
    ),
}


def ler_arquivos_preview(
    numero: str,
    estado: str,
    tipo: TipoProcesso = TipoProcesso.SENTENCA
) -> Dict[str, Any]:
    """
    Le os arquivos de artefatos de um processo para preview.

    Args:
        numero: Numero do processo
        estado: Estado atual do processo
        tipo: Tipo de processo (sentenca/decisao)

    Returns:
        Dict com:
        - Campos legados (analise, minuta)
        - artefatos_disponiveis: lista de artefatos encontrados com metadados
        - minutas_disponiveis: lista de minutas encontradas com metadados
    """
    # Campos legados para compatibilidade
    resultado = {
        "analise": "",
        "minuta": "",
        # Novos campos para artefatos (painel esquerdo)
        "artefatos_disponiveis": [],
        "artefatos": {},
        # Novos campos para minutas (painel direito)
        "minutas_disponiveis": [],
        "minutas": {},
        # Relatorio de precedentes em HTML, quando o trilho de pesquisa o gerou
        "relatorio_precedentes": None
    }

    try:
        pasta = get_pasta_estado(tipo, estado) / numero

        if not pasta.exists():
            return resultado

        arquivos_encontrados = {}

        # Mapear todos os arquivos da pasta
        for arquivo in pasta.iterdir():
            if arquivo.is_file() and arquivo.suffix == ".md":
                arquivos_encontrados[arquivo.name] = arquivo

        # Processar artefatos curados
        for key, (padroes, nome_amigavel, ordem, icone) in ARTEFATOS_CURADOS.items():
            for padrao in padroes:
                # Substituir {numero} pelo numero do processo
                nome_arquivo = padrao.replace("{numero}", numero)

                if nome_arquivo in arquivos_encontrados:
                    arquivo = arquivos_encontrados[nome_arquivo]
                    conteudo = arquivo.read_text(encoding="utf-8")

                    # Guardar conteudo no dict de artefatos
                    resultado["artefatos"][key] = conteudo

                    # Adicionar a lista de disponiveis
                    resultado["artefatos_disponiveis"].append({
                        "key": key,
                        "nome": nome_amigavel,
                        "ordem": ordem,
                        "icone": icone,
                        "arquivo": nome_arquivo
                    })

                    # Manter compatibilidade com campos legados
                    if key == "analise":
                        resultado["analise"] = conteudo

                    break  # Encontrou, nao precisa verificar outros padroes

        # Processar minutas curadas (painel direito)
        for key, (padroes, nome_amigavel, ordem, icone) in MINUTAS_CURADAS.items():
            for padrao in padroes:
                nome_arquivo = padrao.replace("{numero}", numero)

                if nome_arquivo in arquivos_encontrados:
                    arquivo = arquivos_encontrados[nome_arquivo]
                    conteudo = arquivo.read_text(encoding="utf-8")

                    # Guardar conteudo no dict de minutas
                    resultado["minutas"][key] = conteudo

                    # Adicionar a lista de disponiveis
                    resultado["minutas_disponiveis"].append({
                        "key": key,
                        "nome": nome_amigavel,
                        "ordem": ordem,
                        "icone": icone,
                        "arquivo": nome_arquivo
                    })

                    # Manter compatibilidade com campo legado 'minuta'
                    if key == "sentenca":
                        resultado["minuta"] = conteudo

                    break

        # Relatorio de precedentes em HTML (contrato docs/modelo-do-relatorio.md).
        # Nao entra no fluxo de artefatos markdown: e pagina propria, aberta em aba
        # nova - o layout tem 1180px e nao cabe no painel lateral.
        html_precedentes = pasta / f"{numero}-precedentes.html"
        if html_precedentes.is_file():
            resultado["relatorio_precedentes"] = {
                "arquivo": html_precedentes.name,
                "bytes": html_precedentes.stat().st_size,
                "url": f"/api/relatorio-precedentes/{tipo.value}/{estado}/{numero}"
            }

        # Ordenar listas por ordem
        resultado["artefatos_disponiveis"].sort(key=lambda x: x["ordem"])
        resultado["minutas_disponiveis"].sort(key=lambda x: x["ordem"])

        return resultado

    except Exception as e:
        print(f"Erro ao ler arquivos: {e}")
        return resultado


# ============================================================================
# SISTEMA DE NOTAS
# ============================================================================

def ler_nota(
    numero: str,
    estado: str,
    tipo: TipoProcesso = TipoProcesso.SENTENCA
) -> Optional[str]:
    """
    Le a nota de um processo.

    Args:
        numero: Numero do processo
        estado: Estado atual do processo
        tipo: Tipo de processo (sentenca/decisao)

    Returns:
        Conteudo da nota ou None se nao existir
    """
    try:
        pasta = get_pasta_estado(tipo, estado) / numero
        nota_file = pasta / f"{numero}-nota.txt"

        if nota_file.exists():
            conteudo = nota_file.read_text(encoding="utf-8").strip()
            return conteudo if conteudo else None

        return None

    except Exception as e:
        print(f"Erro ao ler nota: {e}")
        return None


def salvar_nota(
    numero: str,
    estado: str,
    tipo: TipoProcesso,
    conteudo: Optional[str]
) -> Dict[str, Any]:
    """
    Salva ou deleta a nota de um processo.

    Args:
        numero: Numero do processo
        estado: Estado atual do processo
        tipo: Tipo de processo
        conteudo: Texto da nota (None ou vazio = deletar)

    Returns:
        Dict com sucesso=True/False e acao realizada
    """
    try:
        pasta = get_pasta_estado(tipo, estado) / numero

        if not pasta.exists():
            return {"sucesso": False, "erro": f"Processo nao encontrado: {numero}"}

        nota_file = pasta / f"{numero}-nota.txt"

        # Deletar se conteudo vazio ou None
        if not conteudo or conteudo.strip() == "":
            if nota_file.exists():
                nota_file.unlink()
            return {"sucesso": True, "acao": "deletada"}

        # Salvar nota
        nota_file.write_text(conteudo.strip(), encoding="utf-8")
        return {"sucesso": True, "acao": "salva"}

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


# ============================================================================
# SISTEMA DE ANEXOS
# ============================================================================

def get_pasta_anexos(tipo: TipoProcesso, estado: str, numero: str) -> Path:
    """Retorna caminho da pasta de anexos de um processo."""
    return get_pasta_estado(tipo, estado) / numero / "anexos"


def formatar_tamanho(bytes_size: int) -> str:
    """Formata tamanho em bytes para exibicao humana."""
    for unidade in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            if unidade == 'B':
                return f"{bytes_size} {unidade}"
            return f"{bytes_size:.1f} {unidade}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def sanitizar_nome_arquivo(nome: str) -> str:
    """Remove caracteres invalidos do nome do arquivo."""
    # Remover caracteres invalidos no Windows
    nome = re.sub(r'[<>:"/\\|?*]', '_', nome)
    # Limitar tamanho
    return nome[:200]


def gerar_nome_unico(pasta: Path, nome: str) -> str:
    """Gera nome unico se arquivo ja existir."""
    if not (pasta / nome).exists():
        return nome

    base = nome.rsplit('.', 1)[0] if '.' in nome else nome
    ext = '.' + nome.rsplit('.', 1)[1] if '.' in nome else ''

    contador = 1
    while (pasta / f"{base}_{contador}{ext}").exists():
        contador += 1

    return f"{base}_{contador}{ext}"


def listar_anexos(
    tipo: TipoProcesso,
    estado: str,
    numero: str
) -> Dict[str, Any]:
    """
    Lista todos os anexos de um processo.

    Returns:
        Dict com lista de anexos e total
    """
    try:
        pasta = get_pasta_anexos(tipo, estado, numero)
        anexos = []

        if pasta.exists():
            for arquivo in pasta.iterdir():
                if arquivo.is_file():
                    stat = arquivo.stat()
                    anexos.append({
                        "nome": arquivo.name,
                        "tamanho": stat.st_size,
                        "tamanho_formatado": formatar_tamanho(stat.st_size),
                        "data_modificacao": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "extensao": arquivo.suffix[1:].lower() if arquivo.suffix else ""
                    })

        # Ordenar por nome
        anexos.sort(key=lambda x: x["nome"].lower())

        return {"sucesso": True, "anexos": anexos, "total": len(anexos)}

    except Exception as e:
        return {"sucesso": False, "anexos": [], "total": 0, "erro": str(e)}


def salvar_anexo(
    tipo: TipoProcesso,
    estado: str,
    numero: str,
    nome: str,
    conteudo: bytes
) -> Dict[str, Any]:
    """
    Salva um anexo na pasta do processo.

    Returns:
        Dict com sucesso e info do arquivo salvo
    """
    try:
        # Verificar se pasta do processo existe
        pasta_processo = get_pasta_estado(tipo, estado) / numero
        if not pasta_processo.exists():
            return {"sucesso": False, "erro": f"Processo nao encontrado: {numero}"}

        # Criar pasta de anexos se nao existir
        pasta = get_pasta_anexos(tipo, estado, numero)
        pasta.mkdir(parents=True, exist_ok=True)

        # Sanitizar nome
        nome_seguro = sanitizar_nome_arquivo(nome)

        # Evitar sobrescrita - gerar nome unico se necessario
        nome_seguro = gerar_nome_unico(pasta, nome_seguro)

        # Salvar arquivo
        caminho = pasta / nome_seguro
        caminho.write_bytes(conteudo)

        return {
            "sucesso": True,
            "arquivo": {
                "nome": nome_seguro,
                "tamanho_formatado": formatar_tamanho(len(conteudo))
            }
        }

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


def deletar_anexo(
    tipo: TipoProcesso,
    estado: str,
    numero: str,
    nome_arquivo: str
) -> Dict[str, Any]:
    """
    Remove um anexo do processo.

    Returns:
        Dict com sucesso e mensagem
    """
    try:
        pasta = get_pasta_anexos(tipo, estado, numero)
        caminho = (pasta / nome_arquivo).resolve()

        # Validar que o caminho resolvido esta dentro da pasta de anexos
        if not str(caminho).startswith(str(pasta.resolve())):
            return {"sucesso": False, "erro": "Caminho invalido"}

        if not caminho.exists():
            return {"sucesso": False, "erro": "Arquivo nao encontrado"}

        caminho.unlink()
        return {"sucesso": True, "mensagem": f"Arquivo '{nome_arquivo}' removido"}

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


# ============================================================================
# EDICAO DE ARQUIVOS MARKDOWN
# ============================================================================

def salvar_arquivo_md(
    tipo: TipoProcesso,
    estado: str,
    numero: str,
    nome_arquivo: str,
    conteudo: str
) -> Dict[str, Any]:
    """
    Salva conteudo em um arquivo Markdown do processo.

    Args:
        tipo: Tipo de processo (sentenca/decisao/despacho)
        estado: Estado atual do processo
        numero: Numero do processo
        nome_arquivo: Nome do arquivo (ex: "0814624-28.2019.4.05.8100-analise.md")
        conteudo: Conteudo a ser salvo

    Returns:
        Dict com sucesso=True/False e mensagem
    """
    try:
        # Validar que o estado e valido
        if estado not in config.ESTADOS:
            return {"sucesso": False, "erro": f"Estado invalido: {estado}"}

        # Validar que o arquivo tem extensao .md
        if not nome_arquivo.endswith('.md'):
            return {"sucesso": False, "erro": "Apenas arquivos .md podem ser editados"}

        # Validar que o nome do arquivo nao contem path separators ou traversal
        if '/' in nome_arquivo or '\\' in nome_arquivo or '..' in nome_arquivo:
            return {"sucesso": False, "erro": "Nome de arquivo invalido"}

        # Obter pasta do processo
        pasta = get_pasta_estado(tipo, estado) / numero

        if not pasta.exists():
            return {"sucesso": False, "erro": f"Processo nao encontrado: {numero}"}

        # Construir caminho completo e validar seguranca
        pasta_resolved = pasta.resolve()
        caminho = (pasta / nome_arquivo).resolve()

        # Verificar que o caminho esta dentro da pasta do processo (previne path traversal)
        try:
            caminho.relative_to(pasta_resolved)
        except ValueError:
            return {"sucesso": False, "erro": "Caminho invalido"}

        # Salvar arquivo com encoding UTF-8
        caminho.write_text(conteudo, encoding="utf-8")

        return {
            "sucesso": True,
            "mensagem": f"Arquivo '{nome_arquivo}' salvo com sucesso",
            "caminho": str(caminho)
        }

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}
