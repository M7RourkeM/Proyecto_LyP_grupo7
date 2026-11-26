"""Pruebas de registro de tiquetes: diagnostico, correlacion masiva, recurrencia
y comportamiento cuando Prolog no esta disponible."""

import shutil

import pytest
from sqlalchemy import func, select

from app.config import Configuracion
from app.main import app
from app.models import Tiquete
from app.prolog.adaptador_subprocess import AdaptadorSubprocess
from app.prolog.fabrica import obtener_adaptador

pytestmark = pytest.mark.skipif(shutil.which("swipl") is None, reason="SWI-Prolog no instalado")

# En la semilla: usuarios 1-2 en finanzas, 3-4 en ventas; activo 1 es la laptop del usuario 1.
RED_INDIVIDUAL = {"usuario_id": 3, "activo_id": 3, "servicio": "red", "componente": "red_cableada",
                  "sintomas": ["sin_internet", "vpn_caida"], "alcance": "individual",
                  "urgencia": "media"}
CORREO = {"usuario_id": 1, "servicio": "correo", "sintomas": ["no_recibe_correos"],
          "alcance": "individual", "urgencia": "media"}


def crear(api, **cambios) -> dict:
    respuesta = api.post("/tiquetes", json={**RED_INDIVIDUAL, **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


# --- Registro con diagnostico ------------------------------------------------

def test_escenario_1_queda_registrado_en_primer_nivel(api):
    respuesta = crear(api)
    tiquete = respuesta["tiquete"]
    assert tiquete["estado"] == "registrado"
    assert tiquete["prioridad"] == "p3" and tiquete["nivel"] == 1
    assert tiquete["categoria"] == "red"
    diagnostico = tiquete["diagnostico"]
    assert diagnostico["causa_principal"] == "cable_desconectado"
    assert [c["id"] for c in diagnostico["causas"]][:2] == ["cable_desconectado",
                                                           "dhcp_sin_respuesta"]
    assert [p["orden"] for p in diagnostico["pasos"]] == [1, 2, 3]
    assert len(tiquete["historial"]) == 1
    assert respuesta["aviso"] is None


def test_datos_del_reporte_se_clasifican_con_el_catalogo_del_motor(api):
    tiquete = crear(api, sintomas=["sin_internet", "usa_wifi"])["tiquete"]
    tipos = {d["codigo"]: d["tipo"] for d in tiquete["datos_reporte"]}
    assert tipos == {"sin_internet": "sintoma", "usa_wifi": "evidencia"}


def test_caso_que_el_motor_escala_pasa_a_escalado_automaticamente(api):
    tiquete = crear(api, **{**CORREO, "alcance": "departamento", "urgencia": "alta"})["tiquete"]
    assert tiquete["estado"] == "escalado"
    assert tiquete["prioridad"] == "p1"
    assert tiquete["grupo_resolutor_id"] == 6  # infraestructura
    ultimo = tiquete["historial"][-1]
    assert (ultimo["estado_anterior"], ultimo["estado_nuevo"]) == ("registrado", "escalado")
    assert ultimo["agente_id"] is None and "motor" in ultimo["comentario"]


# --- Correlacion masiva (criterio de salida de la fase) -----------------------

def test_tres_tiquetes_de_correo_del_mismo_departamento_son_problema_masivo(api):
    primero = crear(api, **CORREO)["tiquete"]
    segundo = crear(api, **{**CORREO, "usuario_id": 2})["tiquete"]
    tercero = crear(api, **CORREO)["tiquete"]
    assert primero["diagnostico"]["posible_problema_masivo"] is False
    assert segundo["diagnostico"]["posible_problema_masivo"] is False
    diagnostico = tercero["diagnostico"]
    assert diagnostico["posible_problema_masivo"] is True
    assert diagnostico["tipo_registro"] == "problema"
    assert tercero["tipo_registro"] == "problema"
    assert diagnostico["incidentes_relacionados"] == [primero["id"], segundo["id"]]
    # Aunque cada usuario lo reporto como individual, el motor lo escala.
    assert diagnostico["reglas_aplicadas"][-1] == "escalar_problema_masivo"
    assert tercero["estado"] == "escalado"
    assert tercero["grupo_resolutor_id"] == 6  # infraestructura


def test_otro_departamento_no_cuenta_para_la_correlacion(api):
    crear(api, **CORREO)
    crear(api, **CORREO)
    en_ventas = crear(api, **{**CORREO, "usuario_id": 3})["tiquete"]
    assert en_ventas["diagnostico"]["posible_problema_masivo"] is False


def test_tiquetes_cerrados_no_cuentan_para_la_correlacion(api, sesion_con_datos):
    for _ in range(2):
        tiquete_id = crear(api, **CORREO)["tiquete"]["id"]
        sesion_con_datos.get(Tiquete, tiquete_id).estado = "cerrado"
    sesion_con_datos.commit()
    assert crear(api, **CORREO)["tiquete"]["diagnostico"]["posible_problema_masivo"] is False


def test_escenario_5_red_masiva_escala_a_redes_y_descarta_el_cable(api):
    for usuario in (3, 4, 3):
        crear(api, usuario_id=usuario)
    tiquete = crear(api, alcance="departamento")["tiquete"]
    diagnostico = tiquete["diagnostico"]
    assert diagnostico["tipo_registro"] == "problema"
    assert diagnostico["posible_problema_masivo"] is True
    assert tiquete["grupo_resolutor_id"] == 2 and tiquete["estado"] == "escalado"  # redes
    assert "cable_desconectado" in {c["id"] for c in diagnostico["causas_descartadas"]}


# --- Recurrencia ---------------------------------------------------------------

def test_tercer_tiquete_de_la_misma_categoria_es_recurrente(api):
    primero = crear(api)
    crear(api)
    tercero = crear(api)
    assert primero["recurrencia"]["usuario"] == {"cantidad": 1, "recurrente": False}
    assert tercero["recurrencia"]["usuario"] == {"cantidad": 3, "recurrente": True}
    assert tercero["recurrencia"]["activo"]["recurrente"] is True


def test_otra_categoria_no_suma_recurrencia(api):
    crear(api)
    crear(api)
    otro = crear(api, servicio="impresoras", sintomas=["no_imprime"], componente=None)
    assert otro["recurrencia"]["usuario"]["cantidad"] == 1


# --- Errores -----------------------------------------------------------------

def test_sintoma_desconocido_es_422_y_no_crea_tiquete(api, sesion_con_datos):
    respuesta = api.post("/tiquetes", json={**RED_INDIVIDUAL, "sintomas": ["tostadora_rota"]})
    assert respuesta.status_code == 422
    assert respuesta.json()["desconocidos"] == ["tostadora_rota"]
    assert sesion_con_datos.scalar(select(func.count()).select_from(Tiquete)) == 0


def test_referencias_invalidas_son_422(api):
    assert api.post("/tiquetes", json={**RED_INDIVIDUAL, "usuario_id": 999}).status_code == 422
    assert api.post("/tiquetes", json={**RED_INDIVIDUAL, "activo_id": 999}).status_code == 422
    api.patch("/usuarios/3", json={"activo": False})
    assert api.post("/tiquetes", json=RED_INDIVIDUAL).status_code == 422


def test_formato_de_sintoma_invalido_es_422(api):
    respuesta = api.post("/tiquetes", json={**RED_INDIVIDUAL, "sintomas": ["Sin Internet!"]})
    assert respuesta.status_code == 422


# --- Prolog no disponible ----------------------------------------------------

def test_prolog_caido_registra_el_tiquete_y_permite_reintentar(api):
    caido = AdaptadorSubprocess(Configuracion(swipl_ejecutable="swipl_inexistente_123"))
    app.dependency_overrides[obtener_adaptador] = lambda: caido
    respuesta = api.post("/tiquetes", json=RED_INDIVIDUAL)
    assert respuesta.status_code == 201
    tiquete = respuesta.json()["tiquete"]
    assert tiquete["diagnostico"] is None
    assert tiquete["nivel"] == 1 and tiquete["grupo_resolutor_id"] == 1  # mesa de ayuda
    assert "/diagnostico" in respuesta.json()["aviso"]

    del app.dependency_overrides[obtener_adaptador]
    reintento = api.post(f"/tiquetes/{tiquete['id']}/diagnostico")
    assert reintento.status_code == 200
    assert reintento.json()["tiquete"]["diagnostico"]["causa_principal"] == "cable_desconectado"
    assert api.post(f"/tiquetes/{tiquete['id']}/diagnostico").status_code == 409


# --- Consulta ------------------------------------------------------------------

def test_listado_filtra_por_estado_y_detalle_trae_historial(api):
    crear(api)
    crear(api, **{**CORREO, "alcance": "departamento", "urgencia": "alta"})
    escalados = api.get("/tiquetes", params={"estado": "escalado"}).json()
    assert escalados["total"] == 1
    tiquete_id = escalados["items"][0]["id"]
    assert len(api.get(f"/tiquetes/{tiquete_id}/historial").json()) == 2
    assert api.get("/tiquetes/999").status_code == 404
