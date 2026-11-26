"""Punto de entrada de la API de la Mesa de Servicios."""

import logging

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from app.config import Configuracion, obtener_configuracion
from app.services.salud import estado_general

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Asistente de Diagnostico y Soporte de TI",
    description="Backend de la mesa de servicios: diagnostico con Prolog e IA generativa local.",
    version="0.1.0",
)


class EstadoSalud(BaseModel):
    api: str = Field(examples=["ok"])
    prolog: str = Field(description="ok | caido", examples=["ok"])
    ia: str = Field(description="ok | caido", examples=["ok"])


@app.get("/salud", response_model=EstadoSalud, tags=["sistema"],
         summary="Estado de la API y de sus dependencias")
async def salud(config: Configuracion = Depends(obtener_configuracion)) -> dict[str, str]:
    """Siempre responde 200; las dependencias caidas se informan como "caido"."""
    return await estado_general(config)
