from pathlib import Path
from enum import Enum


class TipoProcesso(str, Enum):
    """Tipo de processo para gerenciamento no Kanban."""
    SENTENCA = "sentenca"
    DECISAO = "decisao"
    DESPACHO = "despacho"
    VOTO = "voto"


# Caminho base onde estao as pastas de processos
# Aponta para a pasta data/ do projeto superjurista
BASE_PATH = Path(__file__).parent.parent.parent / "data"

# Tipos de processo disponiveis
TIPOS_PROCESSO = [TipoProcesso.SENTENCA, TipoProcesso.DECISAO, TipoProcesso.DESPACHO, TipoProcesso.VOTO]

# Estados do fluxo (nome da pasta)
ESTADOS = {
    "por-analisar": "01-por-analisar",
    "analisando": "02-analisando",
    "pendencias": "03-pendencias",
    "validado": "04-validado",
    "arquivado": "05-arquivados",
}

# Ordem dos estados para exibicao (arquivado nao aparece no kanban)
ORDEM_ESTADOS = ["por-analisar", "analisando", "pendencias", "validado"]

# Sufixos dos arquivos exibidos no preview
ARQUIVOS_PREVIEW = ["-analise.md", "-minuta.md", "-sentenca.md", "-fundamentacao.md", "-relatorio.md"]
