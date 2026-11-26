"""Configuracion de la aplicacion, leida desde variables de entorno o .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Carpeta backend/ (este archivo esta en backend/app/config.py).
DIR_BACKEND = Path(__file__).resolve().parent.parent
KB_POR_DEFECTO = DIR_BACKEND / "app" / "prolog" / "kb" / "motor_inferencia.pl"


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DIR_BACKEND / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de datos
    database_url: str = f"sqlite:///{(DIR_BACKEND / 'mesa_servicios.db').as_posix()}"

    # Prolog
    prolog_adaptador: Literal["subprocess", "pyswip"] = "subprocess"
    prolog_kb: Path = KB_POR_DEFECTO
    swipl_ejecutable: str = "swipl"
    prolog_timeout_s: float = 10.0

    # IA generativa (Ollama local)
    ollama_url: str = "http://localhost:11434"
    ollama_modelo: str = "qwen2.5:3b"
    ollama_timeout_s: float = 60.0

    # Chequeo de salud: tiempo maximo por dependencia
    salud_timeout_s: float = 3.0

    def ruta_kb(self) -> Path:
        """Ruta absoluta de la base de conocimiento; las relativas parten de backend/."""
        ruta = self.prolog_kb
        return ruta if ruta.is_absolute() else (DIR_BACKEND / ruta).resolve()


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
