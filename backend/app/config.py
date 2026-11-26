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
    # La primera respuesta incluye cargar el modelo en memoria: puede tardar.
    ollama_timeout_s: float = 120.0
    # Tiempo que Ollama mantiene el modelo cargado despues de cada consulta.
    ollama_keep_alive: str = "30m"
    # Baja temperatura: textos mas predecibles y apegados al diagnostico.
    ollama_temperatura: float = 0.2
    # false: no se llama a Ollama y se usa siempre la plantilla.
    ia_habilitada: bool = True

    # Correlacion masiva: se buscan tiquetes abiertos del mismo departamento
    # creados en las ultimas N horas.
    correlacion_horas: int = 24
    # Recurrencia: mismo usuario o activo con la misma categoria al menos
    # recurrencia_minimo veces en recurrencia_dias dias.
    recurrencia_minimo: int = 3
    recurrencia_dias: int = 30

    # Jornada laboral para medir el SLA en horas habiles (lunes a viernes).
    # Costa Rica no tiene horario de verano: basta un desfase fijo respecto a UTC.
    jornada_inicio_hora: int = 8
    jornada_fin_hora: int = 16
    zona_horaria_utc_offset: int = -6

    # Chequeo de salud: tiempo maximo por dependencia
    salud_timeout_s: float = 3.0

    def ruta_kb(self) -> Path:
        """Ruta absoluta de la base de conocimiento; las relativas parten de backend/."""
        ruta = self.prolog_kb
        return ruta if ruta.is_absolute() else (DIR_BACKEND / ruta).resolve()


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
