"""Importa todos los modelos para que queden registrados en Base.metadata."""

from app.models.diagnostico import Diagnostico, PasoDiagnostico
from app.models.organizacion import Activo, Agente, Departamento, GrupoResolutor, Usuario
from app.models.tiquete import DatoReporte, HistorialTiquete, Retroalimentacion, Tiquete

__all__ = [
    "Activo", "Agente", "DatoReporte", "Departamento", "Diagnostico", "GrupoResolutor",
    "HistorialTiquete", "PasoDiagnostico", "Retroalimentacion", "Tiquete", "Usuario",
]
