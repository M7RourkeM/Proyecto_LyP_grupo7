"""Crea tiquetes de ejemplo con fechas pasadas para el panel de indicadores.

Los tiquetes se crean con el mismo servicio que usa la API (correlacion +
motor Prolog); la guia y la nota salen de la plantilla para no depender de
Ollama. Despues se mueven en el tiempo y por el ciclo de vida para tener
casos resueltos dentro y fuera de SLA, escalados, abiertos, vencidos,
recurrentes y con retroalimentacion.

Uso (desde la carpeta backend, despues de scripts.seed):
    .venv\\Scripts\\python -m scripts.seed_tiquetes
"""

from datetime import datetime, time, timedelta

from sqlalchemy import select

from app.config import obtener_configuracion
from app.database import SesionLocal
from app.models import GrupoResolutor, Tiquete
from app.prolog.fabrica import crear_adaptador
from app.schemas.seguimiento import RetroalimentacionCrear
from app.schemas.tiquetes import TiqueteCrear
from app.services import ciclo_vida, diagnostico_service, retroalimentacion
from app.services.horas_habiles import Jornada

# Cada caso: datos del tiquete, cuando se creo (dia habil relativo al lunes de
# referencia y hora local), y que paso despues. Agentes: 1-2 mesa de ayuda,
# 3 redes, 4 infraestructura.
CASOS = [
    {"datos": {"usuario_id": 3, "activo_id": 3, "servicio": "red", "componente": "red_cableada",
               "sintomas": ["sin_internet", "vpn_caida"], "alcance": "individual",
               "urgencia": "media"},
     "creado": (0, 9), "flujo": [("en_atencion", 1, 0.5), ("resuelto", 1, 2), ("cerrado", 1, 3)],
     "retro": {"funciono": True, "paso_que_resolvio": "cable_desconectado_2"}},
    {"datos": {"usuario_id": 5, "activo_id": 5, "servicio": "cuentas",
               "sintomas": ["cuenta_bloqueada"], "alcance": "individual", "urgencia": "media"},
     "creado": (0, 10), "flujo": [("en_atencion", 2, 0.25), ("resuelto", 2, 1)],
     "retro": {"funciono": True, "paso_que_resolvio": "intentos_fallidos_2"}},
    {"datos": {"usuario_id": 9, "servicio": "impresoras", "sintomas": ["no_imprime"],
               "alcance": "individual", "urgencia": "baja"},
     "creado": (1, 14), "flujo": [("en_atencion", 1, 1), ("resuelto", 1, 20)],
     "retro": {"funciono": False}},
    # P1 de correo: el motor lo escala; se resuelve en 6 h habiles con SLA de 4 h (incumple).
    {"datos": {"usuario_id": 1, "servicio": "correo", "sintomas": ["no_recibe_correos"],
               "alcance": "departamento", "urgencia": "alta"},
     "creado": (2, 8), "flujo": [("en_atencion", 4, 1), ("resuelto", 4, 6)],
     "retro": {"funciono": True}},
    {"datos": {"usuario_id": 3, "activo_id": 3, "servicio": "red", "sintomas": ["sin_internet"],
               "alcance": "individual", "urgencia": "media"},
     "creado": (3, 9), "flujo": [("en_atencion", 1, 1), ("resuelto", 1, 3)],
     "retro": {"funciono": True, "paso_que_resolvio": "cable_desconectado_1"}},
    # Tercer caso de red del usuario 3: recurrente. Queda abierto.
    {"datos": {"usuario_id": 3, "activo_id": 3, "servicio": "red", "sintomas": ["sin_internet"],
               "alcance": "individual", "urgencia": "media"},
     "creado": (4, 9), "flujo": [("en_atencion", 2, 0.5)]},
    # Abierto desde hace dias: supera su SLA (vencido).
    {"datos": {"usuario_id": 6, "servicio": "cuentas", "sintomas": ["credenciales_rechazadas"],
               "alcance": "individual", "urgencia": "media"},
     "creado": (1, 9), "flujo": []},
    {"datos": {"usuario_id": 10, "servicio": "apps_negocio", "sintomas": ["app_no_responde"],
               "alcance": "departamento", "urgencia": "alta"},
     "creado": (4, 11), "flujo": []},
    {"datos": {"usuario_id": 7, "activo_id": 7, "servicio": "sistema_operativo",
               "sintomas": ["equipo_lento"], "alcance": "individual", "urgencia": "baja"},
     "creado": (4, 14), "flujo": []},
    {"datos": {"usuario_id": 2, "servicio": "nube", "sintomas": ["error_acceso_nube"],
               "alcance": "individual", "urgencia": "media"},
     "creado": (4, 15), "flujo": [("en_atencion", 2, 0.5)]},
]


def lunes_de_referencia(jornada: Jornada) -> datetime:
    """Lunes a las 00:00 (hora local) de hace dos semanas, para que todo quede en el pasado."""
    hoy = datetime.now(jornada.zona).date()
    lunes = hoy - timedelta(days=hoy.weekday() + 14)
    return datetime.combine(lunes, time(0), jornada.zona)


def mover_en_el_tiempo(tiquete: Tiquete, creado: datetime) -> None:
    tiquete.creado_en = creado
    for registro in tiquete.historial:
        registro.fecha = creado


def aplicar_flujo(sesion, tiquete: Tiquete, creado: datetime, flujo: list) -> None:
    """flujo: (estado, agente, horas despues de creado). Las horas son de reloj y
    caen dentro de la jornada para que el calculo habil sea facil de seguir."""
    for estado, agente, horas in flujo:
        if estado == "en_atencion" and tiquete.estado == "resuelto":
            continue
        ciclo_vida.transicionar(sesion, tiquete, estado, agente_id=agente,
                                comentario="Movimiento de ejemplo")
        momento = creado + timedelta(hours=horas)
        tiquete.historial[-1].fecha = momento
        if estado == "resuelto":
            tiquete.resuelto_en = momento
        if estado == "cerrado":
            tiquete.cerrado_en = momento


def main() -> None:
    config = obtener_configuracion()
    adaptador = crear_adaptador(config)
    lunes = lunes_de_referencia(Jornada.desde_config(config))
    with SesionLocal() as sesion:
        if sesion.scalar(select(Tiquete.id)) is not None:
            raise SystemExit("La base ya tiene tiquetes. Corra primero scripts.seed para reiniciarla.")
        if sesion.scalar(select(GrupoResolutor.id)) is None:
            raise SystemExit("La base no tiene datos. Corra primero scripts.seed.")
        for caso in CASOS:
            dia, hora = caso["creado"]
            creado = lunes + timedelta(days=dia, hours=hora)
            tiquete, aviso = diagnostico_service.crear_tiquete(
                sesion, TiqueteCrear(**caso["datos"]), adaptador, config, cliente_ia=None)
            if aviso:
                raise SystemExit(f"Prolog no respondio al crear los tiquetes: {aviso}")
            mover_en_el_tiempo(tiquete, creado)
            aplicar_flujo(sesion, tiquete, creado, caso["flujo"])
            sesion.commit()
            if "retro" in caso:
                retroalimentacion.registrar(sesion, tiquete, RetroalimentacionCrear(**caso["retro"]))
        print(f"Tiquetes de ejemplo creados: {len(CASOS)} (semana del {lunes:%d/%m/%Y}).")


if __name__ == "__main__":
    main()
