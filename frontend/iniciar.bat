@echo off
title SuperJurista Kanban
color 0A

echo.
echo ================================================
echo    SuperJurista - Inteligencia Aumentada
echo    Kanban de Processos Judiciais
echo ================================================
echo.

:: Verificar se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo Instale Python 3.10+ em https://python.org
    pause
    exit /b 1
)

:: Ir para o diretorio do script
cd /d "%~dp0"

:: Verificar se dependencias estao instaladas
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando dependencias...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias!
        pause
        exit /b 1
    )
    echo.
)

:: Verificar se migracao ja foi feita
if not exist "..\data\sentenca\01-por-analisar" (
    echo [INFO] Estrutura de pastas nao encontrada.
    echo.
    echo Deseja executar a migracao de dados? (S/N^)
    set /p MIGRAR="> "
    if /i "%MIGRAR%"=="S" (
        echo.
        echo Executando migracao...
        python migrar_dados.py --executar
        echo.
    )
)

:: Iniciar servidor
echo.
echo [INFO] Iniciando servidor em http://localhost:5000
echo [INFO] Pressione Ctrl+C para parar
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 5000 --reload

pause
