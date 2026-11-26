"""Retroalimentacion: si la solucion funciono y que paso lo resolvio.

Alimenta la base de conocimiento de dos formas:
  - En cada diagnostico, el backend le pasa al motor los resultados
    historicos (resultado_solucion/2), que ajustan el ranking de causas.
  - El Integrante 1 puede descargar las estadisticas o los hechos Prolog
    para revisar la base (GET /retroalimentacion/...).
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Diagnostico, PasoDiagnostico, Retroalimentacion, Tiquete
from app.schemas.seguimiento import (EfectividadCausa, EfectividadPaso,
                                     EstadisticasRetroalimentacion, RetroalimentacionCrear)

ESTADOS_CON_SOLUCION = ("resuelto", "cerrado")


class RetroalimentacionNoPermitida(Exception):
    """El tiquete no admite retroalimentacion en su estado actual (409)."""


class DatosRetroalimentacionInvalidos(Exception):
    """El paso indicado no es valido para el tiquete (422)."""


def registrar(sesion: Session, tiquete: Tiquete,
              datos: RetroalimentacionCrear) -> Retroalimentacion:
    if tiquete.estado not in ESTADOS_CON_SOLUCION:
        raise RetroalimentacionNoPermitida(
            f"El tiquete esta {tiquete.estado}; la retroalimentacion se registra cuando se "
            "resuelve o se cierra")
    if sesion.scalar(select(Retroalimentacion.id).where(
            Retroalimentacion.tiquete_id == tiquete.id)) is not None:
        raise RetroalimentacionNoPermitida(f"El tiquete {tiquete.id} ya tiene retroalimentacion")
    paso = _paso_del_tiquete(tiquete, datos)
    registro = Retroalimentacion(tiquete_id=tiquete.id, funciono=datos.funciono,
                                 paso=paso, comentario=datos.comentario)
    sesion.add(registro)
    sesion.commit()
    return registro


def _paso_del_tiquete(tiquete: Tiquete, datos: RetroalimentacionCrear) -> PasoDiagnostico | None:
    if datos.paso_que_resolvio is None:
        return None
    if not datos.funciono:
        raise DatosRetroalimentacionInvalidos(
            "Si la solucion no funciono, no se indica paso_que_resolvio")
    pasos = tiquete.diagnostico.pasos if tiquete.diagnostico else []
    for paso in pasos:
        if paso.codigo == datos.paso_que_resolvio:
            return paso
    validos = ", ".join(p.codigo for p in pasos) or "ninguno (el tiquete no tiene diagnostico)"
    raise DatosRetroalimentacionInvalidos(
        f"paso_que_resolvio: {datos.paso_que_resolvio} no es un paso de este tiquete. "
        f"Pasos validos: {validos}")


def _filas(sesion: Session):
    """(causa principal, funciono, codigo del paso que resolvio) de cada retroalimentacion."""
    return sesion.execute(
        select(Diagnostico.causa_principal, Retroalimentacion.funciono, PasoDiagnostico.codigo)
        .join(Retroalimentacion, Retroalimentacion.tiquete_id == Diagnostico.tiquete_id)
        .outerjoin(PasoDiagnostico, PasoDiagnostico.id == Retroalimentacion.paso_que_resolvio_id)
        .where(Diagnostico.causa_principal != "sin_determinar")).all()


def estadisticas(sesion: Session) -> EstadisticasRetroalimentacion:
    filas = _filas(sesion)
    por_causa: dict[str, Counter] = defaultdict(Counter)
    for causa, funciono, _ in filas:
        por_causa[causa]["si" if funciono else "no"] += 1
    pasos = Counter(paso for _, funciono, paso in filas if funciono and paso)
    return EstadisticasRetroalimentacion(
        total=len(filas),
        por_causa=[EfectividadCausa(
            causa=causa, casos=c["si"] + c["no"], funciono=c["si"], no_funciono=c["no"],
            efectividad=round(100 * c["si"] / (c["si"] + c["no"]), 1))
            for causa, c in sorted(por_causa.items())],
        por_paso=[EfectividadPaso(paso=p, veces_que_resolvio=n) for p, n in pasos.most_common()])


def hechos_prolog(sesion: Session) -> str:
    """Las retroalimentaciones como hechos resultado_solucion/2 del motor."""
    lineas = [
        "% Retroalimentacion exportada desde la mesa de servicios.",
        f"% Generado: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
        "% resultado_solucion(Causa, si | no).",
        ":- dynamic resultado_solucion/2.",
    ]
    lineas += [f"resultado_solucion({causa}, {'si' if funciono else 'no'})."
               for causa, funciono, _ in _filas(sesion)]
    return "\n".join(lineas) + "\n"
