"""
Chat JULIA - Interface conversacional para pesquisa de jurisprudência do TRF5.

Arquitetura com sessões persistentes:
- WebSocket para comunicação bidirecional em tempo real
- Processo Claude Code dedicado por sessão
- Usa --session-id para manter contexto da conversa
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pathlib import Path
from typing import Optional
import subprocess
import asyncio
import uuid
import json
import os
import shutil


router = APIRouter(prefix="/api/julia", tags=["julia"])


def log(msg: str):
    """Log com flush imediato."""
    print(f"[JULIA] {msg}", flush=True)

# Caminho base do projeto
BASE_PATH = Path(__file__).parent.parent.parent

# Gerenciador de sessões ativas
active_sessions: dict[str, dict] = {}


def get_claude_cli_path() -> str:
    """Retorna o caminho do Claude CLI."""
    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    known_paths = [
        os.path.expanduser("~\\AppData\\Roaming\\npm\\claude.cmd"),
        os.path.expanduser("~\\AppData\\Roaming\\npm\\claude"),
    ]

    for path in known_paths:
        if os.path.exists(path):
            return path

    return "claude"


def get_system_prompt() -> str:
    """Retorna o system prompt para o assistente JULIA."""
    return """Você é o assistente JULIA, pesquisador de jurisprudência do TRF5.

Use ToolSearch para carregar as ferramentas antes de usá-las.

# COMPORTAMENTO PADRÃO

**SEMPRE use `relatorio_segundo_grau` com `extrair_ementas=true` como primeira opção.**
- Isso retorna acórdãos do TRF5 com ementas completas
- Só use outras ferramentas se o usuário pedir explicitamente 1º grau, sentenças ou estatísticas

# FERRAMENTAS

| Tool | Quando Usar | Output |
|------|-------------|--------|
| relatorio_segundo_grau | **PADRÃO** - Acórdãos TRF5 com ementas | Ementas completas |
| relatorio_primeiro_grau | Só se pedir sentenças/1º grau | Estatísticas por juiz |
| buscar_julia | Buscas com filtros específicos | XML estruturado |

# INTELIGÊNCIA DE NOMES

Quando o usuário mencionar um nome de magistrado (desembargador ou juiz):

1. **Extraia o sobrenome principal** e busque variações:
   - "fernando braga" → relator="Fernando Braga" OU relator="Braga"
   - "rogério fialho" → relator="Rogério Fialho" OU relator="Fialho"

2. **Estratégia de busca por nome:**
   - Primeiro: busque SEM filtro de relator, com termo sobre o assunto
   - Analise os resultados para descobrir o nome completo correto
   - Depois: refine com o nome completo se necessário

3. **Desembargadores TRF5 (nomes comuns exemplos):**
   - Fernando Braga Damasceno
   - Rogério de Meneses Fialho Moreira
   - Manoel de Oliveira Erhardt
   - Leonardo Henrique de Cavalcante Carvalho
   - Cid Marconi Gurgel de Souza
   - Paulo Roberto de Oliveira Lima
   - Ivan Lira de Carvalho
   - Vladimir Souza Carvalho
   - Edilson Pereira Nobre Júnior
   - Rubens de Mendonça Canuto Neto
   - Francisco Barros Dias
   - Frederico Wildson da Silva Dantas
   - Paulo Machado Cordeiro
   - Lázaro Guimarães

4. **Se nome não encontrado:**
   - Informe ao usuário que não localizou decisões com aquele nome
   - Sugira buscar apenas pelo tema sem filtro de relator
   - Pergunte se quer tentar variação do nome

# SINTAXE JULIA (operadores MINÚSCULOS)

| Operador | Descrição | Exemplo |
|----------|-----------|---------|
| e | Ambos obrigatórios | pensão e morte |
| ou | Qualquer um | aposentadoria ou benefício |
| nao | Exclui segundo | servidor nao militar |
| $ | Wildcard | aposentad$ |
| "..." | Frase exata | "pensão por morte" |

**NUNCA** use operadores em MAIÚSCULO - JULIA exige minúsculo!

# TRANSFORMAÇÃO DE QUERY

| Linguagem Natural | Query JULIA |
|-------------------|-------------|
| Pensão homoafetivo | pensão e morte e (homoafetivo ou "união estável") |
| Aposentadoria eletricista | aposentad$ e especial e (eletricista ou "energia elétrica") |
| INSS cessar auxílio sem perícia | "auxílio-doença" e (cessação ou alta) e perícia |
| BPC idoso estrangeiro | (bpc ou loas) e idoso e (estrangeiro ou nacionalidade) |

# FILTROS

| Filtro | Descrição | Valores |
|--------|-----------|---------|
| orgao_julgador | Turma | "1ª TURMA", "2ª TURMA", "3ª TURMA", "4ª TURMA", "PLENO" |
| relator | Desembargador | Nome (parcial aceito) |
| assinador | Juiz 1º grau | Nome (parcial aceito) |
| campo_busca | Onde buscar | ementa, acordao, inteiro_teor |
| data_inicial/final | Período | YYYY-MM-DD |

# ÓRGÃOS TRF5

**2º Grau (PADRÃO):**
- 1ª e 2ª Turmas: Previdenciário, Tributário
- 3ª e 4ª Turmas: Criminal, Administrativo
- Pleno: IRDRs, IACs

**1º Grau (só se solicitado):**
- JFCE, JFRN, JFPB, JFPE, JFAL, JFSE

# FLUXO

1. **Interprete** o pedido (tema + eventual nome de magistrado)
2. **Transforme** em query JULIA com operadores minúsculos com inteligência, refinando a busca para ampliar ou reduzir o escopo quando necessário
3. **Execute** relatorio_segundo_grau(termo=..., extrair_ementas=true)
4. **Se houver nome:** filtre por relator após identificar grafia correta
5. **Apresente:**
   - Contexto: descrição clara do contexto jurídico e da questão jurídica central
   - Tendência (favorável/desfavorável)
   - Fundamento: apresentação dos critérios decisórios principais (ratio decidendi)
   - Precedentes: número, relator, data
   - **Ementas completas** (transcreva trechos relevantes)
   - Divergências entre turmas se houver

Seja didático. Cite números de processos. Transcreva ementas."""


async def run_claude_session(
    session_id: str,
    message: str,
    websocket: WebSocket,
    is_first_message: bool = False
) -> None:
    """
    Executa uma mensagem no Claude Code com sessão persistente.
    Envia respostas em tempo real via WebSocket.
    """
    claude_path = get_claude_cli_path()

    env = os.environ.copy()
    npm_path = os.path.expanduser("~\\AppData\\Roaming\\npm")
    if npm_path not in env.get("PATH", ""):
        env["PATH"] = npm_path + os.pathsep + env.get("PATH", "")

    # Construir comando base
    cmd = [
        claude_path,
        "-p", message,
        "--output-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
        "--allowedTools", "mcp__julia-trf5__buscar_julia,mcp__julia-trf5__relatorio_segundo_grau,mcp__julia-trf5__relatorio_primeiro_grau,mcp__julia-trf5__listar_parametros_julia,ToolSearch",
        "--max-turns", "25"
    ]

    # Primeira mensagem: criar sessão; subsequentes: continuar sessão
    if is_first_message:
        cmd.extend(["--session-id", session_id])
        cmd.extend(["--system-prompt", get_system_prompt()])
    else:
        cmd.extend(["--resume", session_id])

    try:
        # Log do comando
        log(f"Executando: {' '.join(cmd[:5])}...")
        log(f"CWD: {BASE_PATH}")

        # Iniciar processo com buffer maior para linhas longas (10MB)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(BASE_PATH),
            env=env,
            limit=10*1024*1024
        )
        log(f"Processo iniciado, PID: {process.pid}")

        # Ler output em tempo real usando chunks
        full_response = ""
        current_text = ""
        buffer = ""

        while True:
            try:
                # Ler chunks de 64KB com timeout de 2 minutos
                chunk = await asyncio.wait_for(
                    process.stdout.read(65536),
                    timeout=120.0
                )
                if not chunk:
                    log("EOF do processo")
                    break

                buffer += chunk.decode("utf-8", errors="replace")

                # Processar linhas completas no buffer
                while "\n" in buffer:
                    line_str, buffer = buffer.split("\n", 1)
                    line_str = line_str.strip()
                    if not line_str:
                        continue

                    log(f"Linha recebida: {line_str[:100]}...")

                    try:
                        data = json.loads(line_str)
                        event_type = data.get("type", "")

                        if event_type == "assistant":
                            message_content = data.get("message", {})
                            content_blocks = message_content.get("content", [])

                            for block in content_blocks:
                                if block.get("type") == "text":
                                    text = block.get("text", "")
                                    if text and text != current_text:
                                        delta = text[len(current_text):]
                                        current_text = text
                                        full_response = text

                                        await websocket.send_json({
                                            "type": "delta",
                                            "content": delta
                                        })

                        elif event_type == "result":
                            result_text = data.get("result", "")
                            if result_text:
                                full_response = result_text

                    except json.JSONDecodeError:
                        # Linha não é JSON válido
                        pass

            except asyncio.TimeoutError:
                log("Timeout na leitura do processo")
                break
            except Exception as e:
                log(f"Erro ao processar chunk: {e}")
                break

        # Aguardar processo terminar
        await process.wait()

        # Ler stderr se houver
        stderr_output = await process.stderr.read()
        if stderr_output:
            log(f"STDERR: {stderr_output.decode('utf-8', errors='ignore')[:500]}")

        log(f"Processo terminou com código: {process.returncode}")

        # Enviar resposta final
        await websocket.send_json({
            "type": "complete",
            "content": full_response,
            "session_id": session_id
        })
        log("Resposta completa enviada")

    except Exception as e:
        log(f"Erro geral: {e}")
        await websocket.send_json({
            "type": "error",
            "content": f"Erro ao executar Claude: {str(e)}"
        })


@router.websocket("/ws")
async def websocket_julia(websocket: WebSocket):
    """
    WebSocket endpoint para chat JULIA com sessão persistente.

    Protocolo:
    - Cliente envia: {"message": "texto", "session_id": "opcional"}
    - Servidor envia: {"type": "delta|complete|error", "content": "..."}
    """
    await websocket.accept()
    log("WebSocket aceito")

    session_id = None
    is_first_message = True

    try:
        while True:
            # Receber mensagem do cliente
            log("Aguardando mensagem...")
            data = await websocket.receive_json()
            log(f"Mensagem recebida: {data}")
            message = data.get("message", "").strip()

            if not message:
                await websocket.send_json({
                    "type": "error",
                    "content": "Mensagem vazia"
                })
                continue

            # Gerenciar sessão
            client_session_id = data.get("session_id")

            if client_session_id and client_session_id in active_sessions:
                session_id = client_session_id
                is_first_message = False
            elif session_id is None:
                # Criar nova sessão
                session_id = str(uuid.uuid4())
                active_sessions[session_id] = {
                    "created_at": asyncio.get_event_loop().time(),
                    "message_count": 0
                }
                is_first_message = True

            # Atualizar contador
            active_sessions[session_id]["message_count"] += 1

            # Notificar que está processando
            await websocket.send_json({
                "type": "processing",
                "session_id": session_id
            })

            # Executar Claude
            await run_claude_session(
                session_id=session_id,
                message=message,
                websocket=websocket,
                is_first_message=is_first_message
            )

            # Após primeira mensagem, marcar como continuação
            is_first_message = False

    except WebSocketDisconnect:
        log(f"Cliente desconectou. Session: {session_id}")
    except Exception as e:
        log(f"Erro no WebSocket: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"Erro interno: {str(e)}"
            })
        except:
            pass


@router.get("/sessions")
async def list_sessions():
    """Lista sessões ativas (para debug)."""
    return {
        "count": len(active_sessions),
        "sessions": [
            {"id": sid, "messages": info["message_count"]}
            for sid, info in active_sessions.items()
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Remove uma sessão."""
    if session_id in active_sessions:
        del active_sessions[session_id]
        return {"status": "deleted"}
    return {"status": "not_found"}
