from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routes.chat import router as chat_router
from app.routes.sessions import router as sessions_router
from app.routes.monitor import router as monitor_router

from app.config import validar_config, FRONTEND_DIR


for _problema in validar_config():  
    print(f"[config] ATENÇÃO: {_problema}")

app = FastAPI(
    title="Assessor IA",
    description="Assessor financeiro e de agenda com LangChain e LangGraph.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(monitor_router)

@app.get("/health")
def health() -> dict:
    """Verifica se a aplicação está funcionando"""
    
    problemas = validar_config()
    return {
        "status": "ok" if not problemas else "atencao",
        "problemas_de_configuracao": problemas,
    }


if (FRONTEND_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    @app.get("/", tags=["infra"])
    def raiz() -> dict:
        return {
            "message": "Frontend não encontrado. Certifique-se de ter executado 'npm run build' no diretório 'frontend'."
            }
      


