"""Pruebas de la maquina de estados del tiquete."""

import shutil
from itertools import product

import pytest

from app.models.enums import ESTADOS_TIQUETE
from app.models import Tiquete
from app.services.ciclo_vida import TRANSICIONES, TransicionInvalida, transicionar

PERMITIDAS = {
    ("registrado", "en_atencion"), ("registrado", "escalado"),
    ("en_atencion", "escalado"), ("en_atencion", "resuelto"),
    ("escalado", "en_atencion"), ("escalado", "resuelto"),
    ("resuelto", "cerrado"), ("resuelto", "en_atencion"),
}
REQUIERE_SWIPL = pytest.mark.skipif(shutil.which("swipl") is None,
                                    reason="SWI-Prolog no instalado")


def test_la_tabla_de_transiciones_es_la_acordada():
    definidas = {(a, n) for a, destinos in TRANSICIONES.items() for n in destinos}
    assert definidas == PERMITIDAS
    assert TRANSICIONES["cerrado"] == frozenset()


@pytest.mark.parametrize("actual,nuevo",
                         [p for p in product(ESTADOS_TIQUETE, repeat=2) if p not in PERMITIDAS])
def test_toda_transicion_no_permitida_se_rechaza(sesion_con_datos, actual, nuevo):
    tiquete = Tiquete(estado=actual, nivel=2)
    with pytest.raises(TransicionInvalida):
        transicionar(sesion_con_datos, tiquete, nuevo, agente_id=1, grupo_id=2)
    assert tiquete.estado == actual


# --- Por la API -----------------------------------------------------------------

def nuevo_tiquete(api) -> int:
    respuesta = api.post("/tiquetes", json={
        "usuario_id": 3, "servicio": "red", "sintomas": ["sin_internet"],
        "alcance": "individual", "urgencia": "media"})
    return respuesta.json()["tiquete"]["id"]


def mover(api, tiquete_id, estado, **extra):
    return api.post(f"/tiquetes/{tiquete_id}/transiciones", json={"estado": estado, **extra})


@REQUIERE_SWIPL
def test_recorrido_completo_queda_en_el_historial(api):
    t = nuevo_tiquete(api)
    assert mover(api, t, "en_atencion", agente_id=1, comentario="Tomo el caso").status_code == 200
    assert mover(api, t, "escalado", agente_id=1, grupo_resolutor_id=2).status_code == 200
    assert mover(api, t, "en_atencion", agente_id=3).status_code == 200
    assert mover(api, t, "resuelto", agente_id=3, comentario="Se cambio el switch").status_code == 200
    final = mover(api, t, "cerrado", agente_id=3).json()

    assert final["estado"] == "cerrado"
    assert final["resuelto_en"] is not None and final["cerrado_en"] is not None
    assert final["grupo_resolutor_id"] == 2 and final["nivel"] == 2
    pasos = [(h["estado_anterior"], h["estado_nuevo"], h["agente_id"]) for h in final["historial"]]
    assert pasos == [(None, "registrado", None), ("registrado", "en_atencion", 1),
                     ("en_atencion", "escalado", 1), ("escalado", "en_atencion", 3),
                     ("en_atencion", "resuelto", 3), ("resuelto", "cerrado", 3)]
    assert final["historial"][1]["comentario"] == "Tomo el caso"


@REQUIERE_SWIPL
def test_cerrado_a_en_atencion_es_409(api):
    t = nuevo_tiquete(api)
    for estado in ("en_atencion", "resuelto", "cerrado"):
        mover(api, t, estado, agente_id=1)
    respuesta = mover(api, t, "en_atencion", agente_id=1)
    assert respuesta.status_code == 409
    assert "estado final" in respuesta.json()["detail"]


@REQUIERE_SWIPL
def test_transicion_rechazada_no_deja_rastro_en_el_historial(api):
    t = nuevo_tiquete(api)
    assert mover(api, t, "cerrado").status_code == 409
    assert len(api.get(f"/tiquetes/{t}/historial").json()) == 1


@REQUIERE_SWIPL
def test_datos_faltantes_o_invalidos_son_422(api):
    t = nuevo_tiquete(api)
    assert mover(api, t, "en_atencion").status_code == 422  # sin agente
    assert mover(api, t, "en_atencion", agente_id=999).status_code == 422
    assert mover(api, t, "escalado").status_code == 422  # primer nivel sin grupo destino
    assert mover(api, t, "escalado", grupo_resolutor_id=1).status_code == 422  # nivel 1
    assert mover(api, t, "pendiente").status_code == 422  # estado inexistente
    assert mover(api, 999, "en_atencion", agente_id=1).status_code == 404


@REQUIERE_SWIPL
def test_reapertura_borra_la_fecha_de_resolucion(api):
    t = nuevo_tiquete(api)
    mover(api, t, "en_atencion", agente_id=1)
    assert mover(api, t, "resuelto", agente_id=1).json()["resuelto_en"] is not None
    reabierto = mover(api, t, "en_atencion", agente_id=1, comentario="El usuario reporta que volvio")
    assert reabierto.json()["resuelto_en"] is None
