"""Indicadores del panel y historial por usuario o activo.

Definiciones:
  - abiertos: registrado, en_atencion o escalado.
  - resueltos: resuelto o cerrado.
  - resueltos en primer nivel: resueltos que nunca pasaron por escalado.
  - escalados: tiquetes que pasaron por escalado alguna vez.
  - cumplimiento de SLA: de los resueltos con SLA, cuantos se resolvieron
    dentro de sus horas habiles (desde la creacion hasta la resolucion).
  - abiertos vencidos: abiertos que ya superaron su SLA.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Configuracion
from app.models import GrupoResolutor, Tiquete
from app.schemas.seguimiento import CumplimientoSLA, Historial, Indicadores, RecurrenciaCategoria
from app.services.correlacion import ESTADOS_ABIERTOS
from app.services.horas_habiles import Jornada, horas_habiles

ESTADOS_RESUELTOS = ("resuelto", "cerrado")


def fue_escalado(tiquete: Tiquete) -> bool:
    return any(h.estado_nuevo == "escalado" for h in tiquete.historial)


def horas_hasta_resolver(tiquete: Tiquete, jornada: Jornada) -> float | None:
    if tiquete.resuelto_en is None:
        return None
    return horas_habiles(tiquete.creado_en, tiquete.resuelto_en, jornada)


def calcular(sesion: Session, config: Configuracion, desde: datetime | None = None,
             hasta: datetime | None = None, ahora: datetime | None = None) -> Indicadores:
    consulta = select(Tiquete)
    if desde is not None:
        consulta = consulta.where(Tiquete.creado_en >= desde)
    if hasta is not None:
        consulta = consulta.where(Tiquete.creado_en <= hasta)
    tiquetes = list(sesion.scalars(consulta))
    grupos = dict(sesion.execute(select(GrupoResolutor.id, GrupoResolutor.codigo)).all())
    resueltos = [t for t in tiquetes if t.estado in ESTADOS_RESUELTOS]
    return Indicadores(
        total=len(tiquetes),
        abiertos=sum(t.estado in ESTADOS_ABIERTOS for t in tiquetes),
        resueltos=len(resueltos),
        resueltos_primer_nivel=sum(not fue_escalado(t) for t in resueltos),
        escalados=sum(fue_escalado(t) for t in tiquetes),
        sla=_cumplimiento_sla(tiquetes, Jornada.desde_config(config),
                              ahora or datetime.now(timezone.utc)),
        por_estado=dict(Counter(t.estado for t in tiquetes)),
        por_prioridad=dict(Counter(t.prioridad or "sin_prioridad" for t in tiquetes)),
        por_grupo=dict(Counter(grupos.get(t.grupo_resolutor_id, "sin_grupo") for t in tiquetes)),
        por_tipo_registro=dict(Counter(t.tipo_registro or "sin_clasificar" for t in tiquetes)),
    )


def _cumplimiento_sla(tiquetes: list[Tiquete], jornada: Jornada, ahora: datetime) -> CumplimientoSLA:
    con_sla = [t for t in tiquetes if t.sla_horas_resolucion is not None]
    duraciones = [(t, horas_hasta_resolver(t, jornada)) for t in con_sla
                  if t.estado in ESTADOS_RESUELTOS and t.resuelto_en is not None]
    dentro = sum(horas <= t.sla_horas_resolucion for t, horas in duraciones)
    vencidos = sum(horas_habiles(t.creado_en, ahora, jornada) > t.sla_horas_resolucion
                   for t in con_sla if t.estado in ESTADOS_ABIERTOS)
    return CumplimientoSLA(
        resueltos_con_sla=len(duraciones), dentro_de_sla=dentro,
        porcentaje=round(100 * dentro / len(duraciones), 1) if duraciones else None,
        abiertos_vencidos=vencidos,
        promedio_horas_resolucion=(round(sum(h for _, h in duraciones) / len(duraciones), 2)
                                   if duraciones else None))


def historial(sesion: Session, config: Configuracion, columna, valor: int) -> Historial:
    """Tiquetes de un usuario o de un activo (columna = Tiquete.usuario_id o
    Tiquete.activo_id), con las categorias recurrentes en la ventana configurada."""
    tiquetes = list(sesion.scalars(select(Tiquete).where(columna == valor)
                                   .order_by(Tiquete.creado_en.desc())))
    desde = datetime.now(timezone.utc) - timedelta(days=config.recurrencia_dias)
    recientes = Counter(t.categoria for t in tiquetes if t.categoria and t.creado_en >= desde)
    return Historial(
        total=len(tiquetes), tiquetes=tiquetes,
        recurrencias=[RecurrenciaCategoria(categoria=c, cantidad=n,
                                           recurrente=n >= config.recurrencia_minimo)
                      for c, n in recientes.most_common()],
        ventana_dias=config.recurrencia_dias, minimo_recurrencia=config.recurrencia_minimo)
