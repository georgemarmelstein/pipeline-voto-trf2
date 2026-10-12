from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Optional

from app.config import TipoProcesso, BASE_PATH
from app.file_manager import (
    listar_processos,
    mover_processo,
    ler_arquivos_preview,
    contar_processos_por_tipo,
    ler_nota,
    salvar_nota,
    listar_anexos,
    salvar_anexo,
    deletar_anexo,
    salvar_arquivo_md
)
from app.classificador import (
    gerar_dashboard,
    gerar_pauta,
    filtrar_processos,
    carregar_meta
)
from app.julia_chat import router as julia_router

app = FastAPI(title="SuperJurista Kanban")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estaticos
STATIC_PATH = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")

# Router do Chat JULIA
app.include_router(julia_router)


@app.get("/chat")
async def chat_julia_page():
    """Serve a interface do Chat JULIA (legado)."""
    return FileResponse(STATIC_PATH / "julia-chat.html")


@app.get("/juslia")
async def juslia_page():
    """Serve a interface JUSLIA (nova)."""
    return FileResponse(STATIC_PATH / "juslia-chat.html")


class MoverRequest(BaseModel):
    numero: str
    estado_origem: str
    estado_destino: str
    tipo: str = "sentenca"
    sobrescrever: bool = False


class ArquivarRequest(BaseModel):
    numero: str
    estado_origem: str
    tipo: str = "sentenca"
    sobrescrever: bool = False


@app.get("/")
async def index():
    """Serve a pagina principal."""
    return FileResponse(STATIC_PATH / "index.html")


@app.get("/api/processos")
async def api_listar_processos_todos():
    """Lista todos os processos de todos os tipos."""
    return listar_processos()


@app.get("/api/processos/{tipo}")
async def api_listar_processos(tipo: str):
    """Lista todos os processos de um tipo especifico."""
    try:
        tipo_enum = TipoProcesso(tipo)
        return listar_processos(tipo_enum)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")


@app.get("/api/processos-contagem")
async def api_contagem_processos():
    """Retorna contagem de processos por tipo (para badges)."""
    return contar_processos_por_tipo()


# ============================================================================
# CLASSIFICADOR QUALITATIVO - Dashboard, Pauta e Modo Foco
# ============================================================================

@app.get("/api/dashboard/{tipo}")
async def api_dashboard(tipo: str):
    """
    Retorna estatisticas do dashboard para visao sistemica do acervo.
    """
    try:
        tipo_enum = TipoProcesso(tipo)
        return gerar_dashboard(BASE_PATH, tipo_enum.value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")


@app.get("/api/dashboard")
async def api_dashboard_default():
    """Dashboard padrao (decisoes)."""
    return gerar_dashboard(BASE_PATH, "decisao")


@app.get("/api/pauta/{tipo}")
async def api_pauta(tipo: str, max_itens: int = 20):
    """
    Retorna pauta operacional priorizada para o dia.
    """
    try:
        tipo_enum = TipoProcesso(tipo)
        return gerar_pauta(BASE_PATH, tipo_enum.value, max_itens)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")


@app.get("/api/pauta")
async def api_pauta_default():
    """Pauta padrao (decisoes)."""
    return gerar_pauta(BASE_PATH, "decisao")


class FiltroRequest(BaseModel):
    tipo: str = "decisao"
    tema: Optional[str] = None
    urgencia: Optional[str] = None
    complexidade: Optional[str] = None
    coluna: Optional[str] = None
    dias_concluso_min: Optional[int] = None
    prioridade_legal: Optional[str] = None


@app.post("/api/foco")
async def api_foco(req: FiltroRequest):
    """
    Filtra processos por multiplos criterios (Modo Foco).
    """
    try:
        tipo_enum = TipoProcesso(req.tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {req.tipo}")

    processos = filtrar_processos(
        BASE_PATH,
        tipo=tipo_enum.value,
        tema=req.tema,
        urgencia=req.urgencia,
        complexidade=req.complexidade,
        coluna=req.coluna,
        dias_concluso_min=req.dias_concluso_min,
        prioridade_legal=req.prioridade_legal
    )

    return {
        "total": len(processos),
        "filtros_aplicados": {
            k: v for k, v in req.model_dump().items() if v is not None
        },
        "processos": processos
    }


@app.get("/api/meta/{tipo}/{estado}/{numero:path}")
async def api_meta_processo(tipo: str, estado: str, numero: str):
    """
    Retorna metadados de classificacao de um processo especifico.
    """
    try:
        tipo_enum = TipoProcesso(tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")

    from app.config import ESTADOS
    estado_pasta = ESTADOS.get(estado, estado)
    processo_path = BASE_PATH / tipo_enum.value / estado_pasta / numero

    meta = carregar_meta(processo_path)
    if not meta:
        # Retornar metadados vazios em vez de 404
        return {
            "numero_processo": numero,
            "tema": "",
            "tema_nome": "",
            "urgencia": "normal",
            "dias_conclusos": 0
        }

    return meta


# ============================================================================
# SISTEMA DE NOTAS
# ============================================================================

class NotaRequest(BaseModel):
    numero: str
    estado: str
    tipo: str = "decisao"
    conteudo: Optional[str] = None


@app.get("/api/nota/{tipo}/{estado}/{numero:path}")
async def api_ler_nota(tipo: str, estado: str, numero: str):
    """
    Retorna a nota de um processo, se existir.
    """
    try:
        tipo_enum = TipoProcesso(tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")

    nota = ler_nota(numero, estado, tipo_enum)
    return {"nota": nota}


@app.post("/api/nota")
async def api_salvar_nota(req: NotaRequest):
    """
    Salva ou deleta a nota de um processo.
    """
    try:
        tipo_enum = TipoProcesso(req.tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {req.tipo}")

    resultado = salvar_nota(req.numero, req.estado, tipo_enum, req.conteudo)

    if not resultado["sucesso"]:
        raise HTTPException(status_code=400, detail=resultado["erro"])

    return resultado


# ============================================================================
# SISTEMA DE ANEXOS
# ============================================================================

@app.get("/api/anexos/{tipo}/{estado}/{numero:path}")
async def api_listar_anexos(tipo: str, estado: str, numero: str):
    """Lista anexos de um processo."""
    try:
        tipo_enum = TipoProcesso(tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")

    return listar_anexos(tipo_enum, estado, numero)


@app.post("/api/anexos/{tipo}/{estado}/{numero:path}")
async def api_upload_anexo(
    tipo: str,
    estado: str,
    numero: str,
    file: UploadFile = File(...)
):
    """Faz upload de um anexo."""
    try:
        tipo_enum = TipoProcesso(tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo invalido")

    # Limite de 50MB
    MAX_SIZE = 50 * 1024 * 1024
    conteudo = await file.read()

    if len(conteudo) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Arquivo muito grande (max 50MB)")

    resultado = salvar_anexo(tipo_enum, estado, numero, file.filename, conteudo)

    if not resultado["sucesso"]:
        raise HTTPException(status_code=400, detail=resultado["erro"])

    return resultado


@app.delete("/api/anexos/{tipo}/{estado}/{numero:path}/{nome_arquivo}")
async def api_deletar_anexo(
    tipo: str,
    estado: str,
    numero: str,
    nome_arquivo: str
):
    """Remove um anexo."""
    try:
        tipo_enum = TipoProcesso(tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")

    resultado = deletar_anexo(tipo_enum, estado, numero, nome_arquivo)

    if not resultado["sucesso"]:
        raise HTTPException(status_code=404, detail=resultado["erro"])

    return resultado


# ============================================================================
# LEITURA DE PROCESSOS
# ============================================================================

@app.get("/api/processo/{tipo}/{estado}/{numero:path}")
async def api_ler_processo(tipo: str, estado: str, numero: str):
    """Retorna conteudo dos arquivos de um processo."""
    try:
        tipo_enum = TipoProcesso(tipo)
        resultado = ler_arquivos_preview(numero, estado, tipo_enum)
        return resultado
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")


@app.get("/api/relatorio-precedentes/{tipo}/{estado}/{numero:path}")
async def api_relatorio_precedentes(tipo: str, estado: str, numero: str):
    """Serve o relatorio de precedentes em HTML gerado pelo trilho de pesquisa.

    Pagina autocontida (CSS/JS inline, sem recurso externo) - servida como
    arquivo para abrir em aba propria. So serve o nome canonico dentro da
    pasta do processo: nao aceita caminho arbitrario.
    """
    try:
        tipo_enum = TipoProcesso(tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {tipo}")

    from app.config import ESTADOS
    if estado not in ESTADOS:
        raise HTTPException(status_code=400, detail=f"Estado invalido: {estado}")

    from app.file_manager import get_pasta_estado
    pasta = get_pasta_estado(tipo_enum, estado) / numero
    alvo = pasta / f"{numero}-precedentes.html"
    try:
        # Impede que numero com ".." escape da pasta do tipo/estado.
        alvo.resolve().relative_to(get_pasta_estado(tipo_enum, estado).resolve())
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Caminho invalido")
    if not alvo.is_file():
        raise HTTPException(status_code=404, detail="Relatorio de precedentes nao gerado")
    return FileResponse(alvo, media_type="text/html; charset=utf-8")


# ============================================================================
# EDICAO DE ARQUIVOS MARKDOWN
# ============================================================================

class SalvarArquivoRequest(BaseModel):
    numero: str
    estado: str
    tipo: str = "sentenca"
    nome_arquivo: str
    conteudo: str


@app.post("/api/arquivo")
async def api_salvar_arquivo(req: SalvarArquivoRequest):
    """
    Salva conteudo em um arquivo Markdown do processo.
    Usado para edicao inline no frontend.
    """
    try:
        tipo_enum = TipoProcesso(req.tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {req.tipo}")

    resultado = salvar_arquivo_md(
        tipo_enum,
        req.estado,
        req.numero,
        req.nome_arquivo,
        req.conteudo
    )

    if not resultado["sucesso"]:
        raise HTTPException(status_code=400, detail=resultado["erro"])

    return resultado


@app.post("/api/mover")
async def api_mover_processo(req: MoverRequest):
    """Move processo entre estados."""
    try:
        tipo_enum = TipoProcesso(req.tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {req.tipo}")

    resultado = mover_processo(
        req.numero,
        req.estado_origem,
        req.estado_destino,
        tipo_enum,
        req.sobrescrever
    )

    if not resultado["sucesso"]:
        status_code = 409 if resultado.get("conflito") else 400
        raise HTTPException(status_code=status_code, detail=resultado["erro"])

    return resultado


@app.post("/api/arquivar")
async def api_arquivar_processo(req: ArquivarRequest):
    """Arquiva um processo (move para pasta arquivados)."""
    try:
        tipo_enum = TipoProcesso(req.tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {req.tipo}")

    resultado = mover_processo(
        req.numero,
        req.estado_origem,
        "arquivado",
        tipo_enum,
        req.sobrescrever
    )

    if not resultado["sucesso"]:
        status_code = 409 if resultado.get("conflito") else 400
        raise HTTPException(status_code=status_code, detail=resultado["erro"])

    return resultado


class ArquivarTodosRequest(BaseModel):
    tipo: str = "sentenca"


@app.post("/api/arquivar-todos")
async def api_arquivar_todos(req: ArquivarTodosRequest = ArquivarTodosRequest()):
    """Arquiva todos os processos da coluna validado de um tipo."""
    try:
        tipo_enum = TipoProcesso(req.tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {req.tipo}")

    processos = listar_processos(tipo_enum)
    validados = processos.get("validado", [])

    arquivados = []
    erros = []

    for proc in validados:
        resultado = mover_processo(proc["numero"], "validado", "arquivado", tipo_enum)
        if resultado["sucesso"]:
            arquivados.append(proc["numero"])
        else:
            erros.append({"numero": proc["numero"], "erro": resultado["erro"]})

    return {
        "sucesso": len(erros) == 0,
        "arquivados": len(arquivados),
        "erros": erros
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
