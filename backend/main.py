from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from services.excel_service import (
    carregar_planilha,
    produtos_mais_vendidos,
)


# ============================================================
# APLICAÇÃO
# ============================================================

app = FastAPI(title="Compras Inteligentes")


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CAMINHOS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PROJETO_DIR = BASE_DIR.parent

FRONTEND_DIR = (
    PROJETO_DIR
    / "frontend"
    / "frontend"
)

INDEX_HTML = FRONTEND_DIR / "index.html"


# ============================================================
# VERIFICAÇÃO
# ============================================================

print("========================================")
print("COMPRAS INTELIGENTES")
print("========================================")
print("Backend:", BASE_DIR)
print("Frontend:", FRONTEND_DIR)
print("Index:", INDEX_HTML)
print("Index existe:", INDEX_HTML.exists())
print("========================================")


# ============================================================
# API - PLANILHA
# ============================================================

@app.get("/planilha")
def planilha():
    return carregar_planilha()


# ============================================================
# API - TODOS OS PRODUTOS
# ============================================================

@app.get("/mais-vendidos")
def mais_vendidos():
    return produtos_mais_vendidos()


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@app.get("/")
def inicio():
    return FileResponse(INDEX_HTML)


# ============================================================
# ARQUIVOS DO FRONTEND
# ============================================================

app.mount(
    "/",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True
    ),
    name="frontend",
)