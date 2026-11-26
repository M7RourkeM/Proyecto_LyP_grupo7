"""Punto de entrada de la API de la Mesa de Servicios."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

import app.models  # noqa: F401  (registra los modelos)
from app.config import Configuracion, obtener_configuracion
from app.database import Base, motor
from app.ia.cliente_ollama import ClienteOllama
from app.prolog.adaptador_base import ErrorProlog
from app.routers import activos, agentes, catalogos, prolog, seguimiento, tiquetes, usuarios
from app.routers.prolog import respuesta_error_prolog
from app.services.salud import estado_general

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    # Crea las tablas que falten; no borra datos existentes.
    Base.metadata.create_all(motor)
    # Carga el modelo de IA en segundo plano: la API queda disponible de inmediato.
    config = obtener_configuracion()
    if config.ia_habilitada:
        threading.Thread(target=ClienteOllama(config).precargar, daemon=True).start()
    yield


app = FastAPI(
    title="Asistente de Diagnostico y Soporte de TI",
    description="Backend de la mesa de servicios: diagnostico con Prolog e IA generativa local.",
    version="0.6.0",
    lifespan=ciclo_de_vida,
)

app.include_router(usuarios.router)
app.include_router(agentes.router)
app.include_router(activos.router)
app.include_router(catalogos.router)
app.include_router(tiquetes.router)
app.include_router(seguimiento.router)
app.include_router(prolog.router)
app.add_exception_handler(ErrorProlog, respuesta_error_prolog)


class EstadoSalud(BaseModel):
    api: str = Field(examples=["ok"])
    prolog: str = Field(description="ok | caido", examples=["ok"])
    ia: str = Field(description="ok | caido", examples=["ok"])


@app.get("/salud", response_model=EstadoSalud, tags=["sistema"],
         summary="Estado de la API y de sus dependencias")
async def salud(config: Configuracion = Depends(obtener_configuracion)) -> dict[str, str]:
    """Siempre responde 200; las dependencias caidas se informan como "caido"."""
    return await estado_general(config)
