from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.user import auth_router
from app.cores.db import engine, init_db


origins = [
    "http://localhost:3000",
    "https://ton-domaine.com",
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Démarrage de l'application...")
    await init_db()
    yield
    print("Arrêt de l'application...")
    await engine.dispose()

app = FastAPI(
    title="BestReserv API",
    description="L'API de BestReserv pour la gestion des réservations et des utilisateurs   ", 
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

app.include_router(auth_router, prefix="/api/v1")
 