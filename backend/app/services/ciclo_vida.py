"""Maquina de estados del tiquete.

Flujo principal: registrado -> en_atencion -> escalado -> resuelto -> cerrado.
Ademas se permite resolver en primer nivel (en_atencion -> resuelto), que
un nivel superior tome el caso (escalado -> en_atencion), reabrir
(resuelto -> en_atencion) y escalar al registrar (registrado -> escalado).
Cerrado es un estado final.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Agente, GrupoResolutor, HistorialTiquete, Tiquete

TRANSICIONES: dict[str, frozenset[str]] = {
    "registrado": frozenset({"en_atencion", "escalado"}),
    "en_atencion": frozenset({"escalado", "resuelto"}),
    "escalado": frozenset({"en_atencion", "resuelto"}),
    "resuelto": frozenset({"cerrado", "en_atencion"}),
    "cerrado": frozenset(),
}


class TransicionInvalida(Exception):
    """El cambio de estado no esta permitido desde el estado actual (409)."""


class DatosTransicionInvalidos(Exception):
    """Falta un dato o referencia un registro invalido (422)."""


def registrar_inicio(tiquete: Tiquete, comentario: str) -> None:
    tiquete.estado = "registrado"
    tiquete.historial.append(HistorialTiquete(estado_nuevo="registrado", comentario=comentario))


def transicionar(sesion: Session, tiquete: Tiquete, nuevo: str, agente_id: int | None = None,
                 comentario: str | None = None, grupo_id: int | None = None) -> None:
    """Valida y aplica el cambio de estado, y lo deja en el historial.

    agente_id es None cuando el cambio lo hace el sistema.
    """
    actual = tiquete.estado
    if nuevo not in TRANSICIONES[actual]:
        permitidos = ", ".join(sorted(TRANSICIONES[actual])) or "ninguno (estado final)"
        raise TransicionInvalida(f"No se puede pasar de {actual} a {nuevo}. "
                                 f"Desde {actual} se permite: {permitidos}")
    agente = _validar_agente(sesion, agente_id, obligatorio=(nuevo == "en_atencion"))
    if nuevo == "escalado":
        _asignar_grupo_superior(sesion, tiquete, grupo_id)
    if agente is not None and nuevo == "en_atencion":
        tiquete.agente_id = agente.id
    _actualizar_fechas(tiquete, actual, nuevo)
    tiquete.estado = nuevo
    tiquete.historial.append(HistorialTiquete(estado_anterior=actual, estado_nuevo=nuevo,
                                              agente_id=agente_id, comentario=comentario))


def _validar_agente(sesion: Session, agente_id: int | None, obligatorio: bool) -> Agente | None:
    if agente_id is None:
        if obligatorio:
            raise DatosTransicionInvalidos("Para pasar a en_atencion se debe indicar agente_id")
        return None
    agente = sesion.get(Agente, agente_id)
    if agente is None:
        raise DatosTransicionInvalidos(f"agente_id: no existe un agente con id {agente_id}")
    if not agente.activo:
        raise DatosTransicionInvalidos(f"El agente {agente_id} esta desactivado")
    return agente


def _asignar_grupo_superior(sesion: Session, tiquete: Tiquete, grupo_id: int | None) -> None:
    """Al escalar, el caso debe quedar en un grupo de nivel 2 o 3."""
    if grupo_id is None:
        if (tiquete.nivel or 1) >= 2:
            return  # ya esta asignado a un grupo superior (ej. lo decidio el motor)
        raise DatosTransicionInvalidos(
            "Para escalar un caso de primer nivel se debe indicar grupo_resolutor_id")
    grupo = sesion.get(GrupoResolutor, grupo_id)
    if grupo is None:
        raise DatosTransicionInvalidos(
            f"grupo_resolutor_id: no existe un grupo con id {grupo_id}")
    if grupo.nivel < 2:
        raise DatosTransicionInvalidos("Solo se puede escalar a un grupo de nivel 2 o 3")
    tiquete.grupo_resolutor_id = grupo.id
    tiquete.nivel = grupo.nivel
    tiquete.agente_id = None  # lo toma un agente del nuevo grupo


def _actualizar_fechas(tiquete: Tiquete, actual: str, nuevo: str) -> None:
    ahora = datetime.now(timezone.utc)
    if nuevo == "resuelto":
        tiquete.resuelto_en = ahora
    elif nuevo == "cerrado":
        tiquete.cerrado_en = ahora
    elif actual == "resuelto" and nuevo == "en_atencion":
        tiquete.resuelto_en = None  # reapertura: el SLA vuelve a correr
