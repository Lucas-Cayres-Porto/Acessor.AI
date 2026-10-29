param(
    [string]$Command = "api"
)

switch ($Command.ToLower()) {
    { $_ -in "api", "run", "dev" } {
        Write-Host "Iniciando servidor FastAPI com reload..." -ForegroundColor Cyan
        python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
    }
    "cli" {
        Write-Host "Iniciando assistente no terminal..." -ForegroundColor Cyan
        python -m app.graph
    }
    "install" {
        Write-Host "Instalando dependencias..." -ForegroundColor Cyan
        python -m pip install -r requirements.txt
    }
    "clean" {
        Write-Host "Limpando caches do Python..." -ForegroundColor Cyan
        python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
        Write-Host "Caches removidos com sucesso!" -ForegroundColor Green
    }
    default {
        Write-Host "======================================================" -ForegroundColor Yellow
        Write-Host "Comandos disponiveis:" -ForegroundColor Yellow
        Write-Host "  .\run.ps1          - Inicia o servidor FastAPI (padrao)"
        Write-Host "  .\run.ps1 cli      - Inicia o assistente no terminal"
        Write-Host "  .\run.ps1 install  - Instala dependencias"
        Write-Host "  .\run.ps1 clean    - Limpa caches __pycache__"
        Write-Host "======================================================" -ForegroundColor Yellow
    }
}
