"""Busqueda de incidentes abiertos similares y deteccion de recurrencia.

El backend solo selecciona candidatos con criterios de consulta (mismo
departamento, abiertos, recientes y relacionados con el servicio o los
sintomas). Si eso constituye un problema masivo lo decide el motor Prolog.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.config import Configuracion
from app.models import DatoReporte, Tiquete
from app.schemas.prolog import IncidenteAbierto
from app.schemas.tiquetes import Recurrencia, RecurrenciaTiquete

ESTADOS_ABIERTOS = ("registrado", "en_atencion", "escalado")


def incidentes_similares(sesion: Session, config: Configuracion, departamento_id: int,
                         codigo_departamento: str, servicio: str, sintomas: list[str],
                         excluir_id: int | None = None) -> list[IncidenteAbierto]:
    desde = datetime.now(timezone.utc) - timedelta(hours=config.correlacion_horas)
    comparte_sintoma = exists().where(DatoReporte.tiquete_id == Tiquete.id,
                                      DatoReporte.codigo.in_(sintomas))
    consulta = (select(Tiquete)
                .where(Tiquete.departamento_id == departamento_id,
                       Tiquete.estado.in_(ESTADOS_ABIERTOS),
                       Tiquete.creado_en >= desde,
                       or_(Tiquete.servicio == servicio, comparte_sintoma))
                .order_by(Tiquete.id))
    if excluir_id is not None:
        consulta = consulta.where(Tiquete.id != excluir_id)
    return [
        IncidenteAbierto(id=t.id, departamento=codigo_departamento, estado=t.estado,
                         sintomas=[d.codigo for d in t.datos_reporte if d.tipo == "sintoma"])
        for t in sesion.scalars(consulta)
    ]


def recurrencia(sesion: Session, config: Configuracion, tiquete: Tiquete) -> RecurrenciaTiquete | None:
    """Cuenta tiquetes de la misma categoria del mismo usuario y del mismo activo."""
    if tiquete.categoria is None:
        return None
    desde = datetime.now(timezone.utc) - timedelta(days=config.recurrencia_dias)

    def contar(columna, valor) -> Recurrencia:
        cantidad = sesion.scalar(select(func.count()).select_from(Tiquete).where(
            columna == valor, Tiquete.categoria == tiquete.categoria,
            Tiquete.creado_en >= desde))
        return Recurrencia(cantidad=cantidad, recurrente=cantidad >= config.recurrencia_minimo)

    return RecurrenciaTiquete(
        usuario=contar(Tiquete.usuario_id, tiquete.usuario_id),
        activo=contar(Tiquete.activo_id, tiquete.activo_id) if tiquete.activo_id else None,
        minimo=config.recurrencia_minimo, dias=config.recurrencia_dias)
