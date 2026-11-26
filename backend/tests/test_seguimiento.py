"""Pruebas de retroalimentacion, historial e indicadores."""

import shutil
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Configuracion
from app.models import Tiquete
from app.services import indicadores

pytestmark = pytest.mark.skipif(shutil.which("swipl") is None, reason="SWI-Prolog no instalado")

CR = timezone(timedelta(hours=-6))
RED = {"usuario_id": 3, "activo_id": 3, "servicio": "red", "componente": "red_cableada",
       "sintomas": ["sin_internet"], "alcance": "individual", "urgencia": "media"}
CORREO_P1 = {"usuario_id": 1, "servicio": "correo", "sintomas": ["no_recibe_correos"],
             "alcance": "departamento", "urgencia": "alta"}


def crear(api, datos=RED) -> int:
    respuesta = api.post("/tiquetes", json=datos)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["tiquete"]["id"]


def resolver(api, tiquete_id: int) -> None:
    for estado in ("en_atencion", "resuelto"):
        assert api.post(f"/tiquetes/{tiquete_id}/transiciones",
                        json={"estado": estado, "agente_id": 1}).status_code == 200


def tiquete_resuelto(api, datos=RED) -> int:
    tiquete_id = crear(api, datos)
    resolver(api, tiquete_id)
    return tiquete_id


# --- Retroalimentacion ---------------------------------------------------------

def test_registrar_y_consultar_retroalimentacion(api):
    t = tiquete_resuelto(api)
    creada = api.post(f"/tiquetes/{t}/retroalimentacion", json={
        "funciono": True, "paso_que_resolvio": "cable_desconectado_2", "comentario": "Otro cable"})
    assert creada.status_code == 201
    assert creada.json()["paso_que_resolvio"] == "cable_desconectado_2"
    assert api.get(f"/tiquetes/{t}/retroalimentacion").json()["funciono"] is True


def test_retroalimentacion_solo_en_tiquetes_resueltos_y_una_vez(api):
    abierto = crear(api)
    assert api.post(f"/tiquetes/{abierto}/retroalimentacion",
                    json={"funciono": True}).status_code == 409
    resuelto = tiquete_resuelto(api)
    assert api.post(f"/tiquetes/{resuelto}/retroalimentacion",
                    json={"funciono": True}).status_code == 201
    assert api.post(f"/tiquetes/{resuelto}/retroalimentacion",
                    json={"funciono": False}).status_code == 409


def test_paso_invalido_es_422(api):
    t = tiquete_resuelto(api)
    respuesta = api.post(f"/tiquetes/{t}/retroalimentacion",
                         json={"funciono": True, "paso_que_resolvio": "intentos_fallidos_1"})
    assert respuesta.status_code == 422
    assert "cable_desconectado_1" in respuesta.json()["detail"]  # lista los pasos validos
    respuesta = api.post(f"/tiquetes/{t}/retroalimentacion",
                         json={"funciono": False, "paso_que_resolvio": "cable_desconectado_1"})
    assert respuesta.status_code == 422


def test_retroalimentacion_inexistente_es_404(api):
    assert api.get(f"/tiquetes/{crear(api)}/retroalimentacion").status_code == 404
    assert api.post("/tiquetes/999/retroalimentacion", json={"funciono": True}).status_code == 404


def test_estadisticas_y_hechos_prolog(api):
    for funciono in (True, True, False):
        t = tiquete_resuelto(api)
        api.post(f"/tiquetes/{t}/retroalimentacion", json={"funciono": funciono})
    estadisticas = api.get("/retroalimentacion/estadisticas").json()
    assert estadisticas["total"] == 3
    assert estadisticas["por_causa"] == [{"causa": "cable_desconectado", "casos": 3,
                                          "funciono": 2, "no_funciono": 1, "efectividad": 66.7}]
    hechos = api.get("/retroalimentacion/hechos.pl").text
    assert hechos.count("resultado_solucion(cable_desconectado, si).") == 2
    assert "resultado_solucion(cable_desconectado, no)." in hechos


def test_la_retroalimentacion_cambia_el_diagnostico_siguiente(api):
    """Si la solucion del cable falla varias veces, el motor deja de proponerlo primero."""
    assert api.post("/tiquetes", json=RED).json()["tiquete"]["diagnostico"][
        "causa_principal"] == "cable_desconectado"
    for _ in range(3):
        t = tiquete_resuelto(api)
        api.post(f"/tiquetes/{t}/retroalimentacion", json={"funciono": False})
    nuevo = api.post("/tiquetes", json=RED).json()["tiquete"]["diagnostico"]
    assert nuevo["causa_principal"] == "dhcp_sin_respuesta"


# --- Historial -------------------------------------------------------------------

def test_historial_de_usuario_marca_la_categoria_recurrente(api):
    for _ in range(3):
        crear(api)
    crear(api, {**RED, "servicio": "impresoras", "sintomas": ["no_imprime"], "componente": None})
    historial = api.get("/usuarios/3/historial").json()
    assert historial["total"] == 4
    assert {"categoria": "red", "cantidad": 3, "recurrente": True} in historial["recurrencias"]
    assert {"categoria": "impresoras", "cantidad": 1, "recurrente": False} in historial["recurrencias"]


def test_historial_de_activo(api):
    crear(api)
    crear(api, {**RED, "activo_id": None})
    assert api.get("/activos/3/historial").json()["total"] == 1
    assert api.get("/activos/999/historial").status_code == 404
    assert api.get("/usuarios/999/historial").status_code == 404


# --- Indicadores (SLA verificado a mano) -------------------------------------------

def fijar_fechas(sesion, tiquete_id: int, creado: datetime, resuelto: datetime) -> None:
    tiquete = sesion.get(Tiquete, tiquete_id)
    tiquete.creado_en, tiquete.resuelto_en = creado, resuelto
    sesion.commit()


def test_indicadores_con_sla_calculado_a_mano(api, sesion_con_datos):
    """A (P3, SLA 16 h): jueves 26/11 15:00 -> viernes 27/11 10:00 = 1 + 2 = 3 h, cumple.
    B (P1, SLA 4 h, escalado por el motor): miercoles 25/11 8:00 -> 14:00 = 6 h, incumple.
    Cumplimiento: 1 de 2 = 50 %. Promedio: (3 + 6) / 2 = 4,5 h."""
    a = tiquete_resuelto(api)
    b = tiquete_resuelto(api, CORREO_P1)
    fijar_fechas(sesion_con_datos, a, datetime(2026, 11, 26, 15, tzinfo=CR),
                 datetime(2026, 11, 27, 10, tzinfo=CR))
    fijar_fechas(sesion_con_datos, b, datetime(2026, 11, 25, 8, tzinfo=CR),
                 datetime(2026, 11, 25, 14, tzinfo=CR))
    datos = api.get("/indicadores").json()
    assert datos["sla"] == {"resueltos_con_sla": 2, "dentro_de_sla": 1, "porcentaje": 50.0,
                            "abiertos_vencidos": 0, "promedio_horas_resolucion": 4.5}
    assert datos["resueltos"] == 2 and datos["escalados"] == 1
    assert datos["resueltos_primer_nivel"] == 1
    assert datos["por_prioridad"] == {"p3": 1, "p1": 1}
    assert datos["por_grupo"] == {"mesa_ayuda": 1, "infraestructura": 1}


def test_abierto_que_supera_su_sla_cuenta_como_vencido(api, sesion_con_datos):
    """Creado el lunes 23/11 a las 8:00; al viernes 27/11 a las 8:00 lleva
    4 dias x 8 h = 32 h habiles, mas que su SLA de 16 h."""
    t = crear(api)
    sesion_con_datos.get(Tiquete, t).creado_en = datetime(2026, 11, 23, 8, tzinfo=CR)
    sesion_con_datos.commit()
    resultado = indicadores.calcular(sesion_con_datos, Configuracion(),
                                     ahora=datetime(2026, 11, 27, 8, tzinfo=CR))
    assert resultado.sla.abiertos_vencidos == 1
    assert resultado.sla.porcentaje is None  # todavia no hay resueltos


def test_indicadores_sin_tiquetes_y_filtro_de_fechas(api):
    vacio = api.get("/indicadores").json()
    assert vacio["total"] == 0 and vacio["sla"]["porcentaje"] is None
    crear(api)
    assert api.get("/indicadores", params={"desde": "2099-01-01T00:00:00-06:00"}).json()[
        "total"] == 0
    assert api.get("/indicadores", params={"desde": "2026-01-01T00:00:00"}).status_code == 422
