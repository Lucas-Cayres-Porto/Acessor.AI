@echo off
setlocal

set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=api

if "%COMMAND%"=="api" goto run_api
if "%COMMAND%"=="run" goto run_api
if "%COMMAND%"=="dev" goto run_api
if "%COMMAND%"=="cli" goto run_cli
if "%COMMAND%"=="install" goto run_install
if "%COMMAND%"=="clean" goto run_clean
if "%COMMAND%"=="help" goto show_help

echo Comando desconhecido: %COMMAND%
echo Digite "run help" para ver as opcoes.
goto end

:run_api
echo Iniciando servidor FastAPI com reload...
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
goto end

:run_cli
echo Iniciando fluxo interativo no terminal...
python -m app.graph
goto end

:run_install
echo Instalando dependencias...
python -m pip install -r requirements.txt
goto end

:run_clean
echo Limpando caches do Python...
python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
echo Caches removidos com sucesso!
goto end

:show_help
echo ======================================================
echo Comandos disponiveis:
echo   run             - Inicia o servidor FastAPI (padrao)
echo   run cli         - Inicia o assistente no terminal
echo   run install     - Instala dependencias do requirements.txt
echo   run clean       - Limpa caches __pycache__
echo ======================================================

:end
