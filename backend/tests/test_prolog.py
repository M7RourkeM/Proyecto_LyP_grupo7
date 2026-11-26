"""Pruebas del adaptador de Prolog: escenarios del enunciado, equivalencia
entre adaptadores y manejo de errores."""

import shutil

import pytest

from app.config import Configuracion
from app.prolog.adaptador_base import (EntradaInvalida, PredicadoInexistente, PrologNoDisponible,
                                       PrologTimeout)
from app.prolog.adaptador_pyswip import AdaptadorPyswip
from app.prolog.adaptador_subprocess import AdaptadorSubprocess
from app.schemas.prolog import EntradaDiagnostico, IncidenteAbierto

pytestmark = pytest.mark.skipif(shutil.which("swipl") is None, reason="SWI-Prolog no instalado")


def _pyswip_disponible() -> bool:
    try:
        AdaptadorPyswip(Configuracion())
        return True
    except PrologNoDisponible:
        return False


ADAPTADORES = [AdaptadorSubprocess]
if _pyswip_disponible():
    ADAPTADORES.append(AdaptadorPyswip)


def entrada(sintomas, alcance="individual", urgencia="media", departamento="ventas",
            **extra) -> EntradaDiagnostico:
    return EntradaDiagnostico(servicio="red", sintomas=sintomas, alcance=alcance,
                              urgencia=urgencia, departamento=departamento, **extra)


def incidentes_de_red(cantidad: int) -> list[IncidenteAbierto]:
    return [IncidenteAbierto(id=100 + i, sintomas=["sin_internet"], departamento="ventas",
                             estado="registrado") for i in range(cantidad)]


# Cada escenario: (entrada, incidentes abiertos, resultado esperado minimo)
ESCENARIOS = {
    "1_sin_internet_vpn_individual": (
        entrada(["sin_internet", "vpn_caida"], componente="red_cableada"), [],
        {"causas_ids": ["cable_desconectado", "dhcp_sin_respuesta"], "prioridad": "p3",
         "nivel": 1, "escalar": False, "tipo_registro": "incidente",
         "pasos_ids": ["cable_desconectado_1", "cable_desconectado_2", "cable_desconectado_3"]}),
    "2_correo_departamento": (
        entrada(["no_recibe_correos", "no_envia_correos"], alcance="departamento",
                urgencia="alta", departamento="finanzas"), [],
        {"causas_ids": ["correo_servidor_caido"], "impacto": "departamento", "prioridad": "p1",
         "nivel": 2, "escalar": True, "grupo_resolutor": "infraestructura",
         "descartadas_ids": ["cuota_buzon_llena"]}),
    "3_cuenta_bloqueada": (
        entrada(["cuenta_bloqueada"]), [],
        {"causas_ids": ["intentos_fallidos"], "nivel": 1,
         "pasos_ids": [f"intentos_fallidos_{n}" for n in range(1, 5)]}),
    "3b_cuenta_bloqueada_pasos_agotados": (
        entrada(["cuenta_bloqueada"], pasos_ya_aplicados=["a", "b", "c", "d"]), [],
        {"nivel": 2, "escalar": True, "grupo_resolutor": "cuentas_y_accesos",
         "regla": "escalar_pasos_agotados"}),
    "4_impresora_individual": (
        entrada(["no_imprime"], urgencia="baja"), [],
        {"causas_ids": ["cola_impresion_detenida", "controlador_impresora"], "prioridad": "p4",
         "nivel": 1}),
    "4b_impresora_departamento": (
        entrada(["no_imprime"], alcance="departamento", urgencia="baja"), [],
        {"causas_ids": ["cola_impresion_detenida"], "nivel": 2,
         "grupo_resolutor": "soporte_equipos"}),
    "5_masivo_red_departamento": (
        entrada(["sin_internet", "vpn_caida"], alcance="departamento"), incidentes_de_red(3),
        {"tipo_registro": "problema", "posible_problema_masivo": True, "nivel": 2,
         "grupo_resolutor": "redes", "descartadas_ids": ["cable_desconectado"],
         "incidentes_relacionados": [100, 101, 102]}),
    "sin_causa_aplicable": (
        entrada(["cuenta_bloqueada"], alcance="departamento"), [],
        {"causas_ids": [], "pasos_ids": [], "nivel": 2, "escalar": True,
         "regla": "sin_regla_aplicable"}),
    "sospecha_seguridad": (
        entrada(["cuenta_bloqueada"], sospecha_seguridad=True), [],
        {"nivel": 3, "grupo_resolutor": "ciberseguridad", "urgencia": "alta"}),
}


def verificar(diagnostico, esperado: dict) -> None:
    obtenido = diagnostico.model_dump()
    for clave, valor in esperado.items():
        if clave == "causas_ids":
            assert [c["id"] for c in obtenido["causas"]][:len(valor)] == valor
            if not valor:
                assert obtenido["causas"] == []
        elif clave == "descartadas_ids":
            assert set(valor) <= {c["id"] for c in obtenido["causas_descartadas"]}
        elif clave == "pasos_ids":
            assert [p["id"] for p in obtenido["pasos"]] == valor
            assert [p["orden"] for p in obtenido["pasos"]] == list(range(1, len(valor) + 1))
        elif clave == "regla":
            assert valor in obtenido["reglas_aplicadas"]
        else:
            assert obtenido[clave] == valor, clave


@pytest.mark.parametrize("adaptador", ADAPTADORES, ids=lambda a: a.nombre)
@pytest.mark.parametrize("nombre", list(ESCENARIOS))
def test_escenarios_del_enunciado(adaptador, nombre):
    datos, incidentes, esperado = ESCENARIOS[nombre]
    verificar(adaptador(Configuracion()).diagnosticar(datos, incidentes), esperado)


@pytest.mark.skipif(len(ADAPTADORES) < 2, reason="pyswip no disponible")
def test_ambos_adaptadores_devuelven_exactamente_lo_mismo():
    config = Configuracion()
    for nombre, (datos, incidentes, _) in ESCENARIOS.items():
        por_subprocess = AdaptadorSubprocess(config).diagnosticar(datos, incidentes)
        por_pyswip = AdaptadorPyswip(config).diagnosticar(datos, incidentes)
        assert por_subprocess.model_dump() == por_pyswip.model_dump(), nombre


@pytest.mark.parametrize("adaptador", ADAPTADORES, ids=lambda a: a.nombre)
def test_los_incidentes_temporales_no_quedan_cargados(adaptador):
    motor = adaptador(Configuracion())
    datos = entrada(["sin_internet"], alcance="departamento")
    assert motor.diagnosticar(datos, incidentes_de_red(3)).posible_problema_masivo is True
    assert motor.diagnosticar(datos).posible_problema_masivo is False


@pytest.mark.parametrize("adaptador", ADAPTADORES, ids=lambda a: a.nombre)
def test_sintoma_desconocido_es_entrada_invalida(adaptador):
    with pytest.raises(EntradaInvalida) as error:
        adaptador(Configuracion()).diagnosticar(entrada(["sin_internet", "tostadora_rota"]))
    assert error.value.desconocidos == ["tostadora_rota"]


# --- Errores de infraestructura (solo subprocess: pyswip admite una base por proceso) ---

def test_prolog_no_instalado():
    config = Configuracion(swipl_ejecutable="swipl_inexistente_123")
    with pytest.raises(PrologNoDisponible):
        AdaptadorSubprocess(config).diagnosticar(entrada(["sin_internet"]))


def test_base_de_conocimiento_inexistente(tmp_path):
    config = Configuracion(prolog_kb=tmp_path / "no_existe.pl")
    with pytest.raises(PrologNoDisponible):
        AdaptadorSubprocess(config).diagnosticar(entrada(["sin_internet"]))


def test_base_sin_el_predicado_esperado(tmp_path):
    kb = tmp_path / "incompleta.pl"
    kb.write_text("sintoma(sin_internet, red, 'x').\n", encoding="utf-8")
    with pytest.raises(PredicadoInexistente):
        AdaptadorSubprocess(Configuracion(prolog_kb=kb)).diagnosticar(entrada(["sin_internet"]))


def test_motor_que_no_termina_respeta_el_limite_de_tiempo(tmp_path):
    kb = tmp_path / "ciclo.pl"
    kb.write_text("sintoma(sin_internet, red, 'x').\n"
                  "diagnostico_completo(_, _, _, _) :- repeat, fail.\n", encoding="utf-8")
    config = Configuracion(prolog_kb=kb, prolog_timeout_s=1)
    with pytest.raises(PrologTimeout):
        AdaptadorSubprocess(config).diagnosticar(entrada(["sin_internet"]))


# --- Endpoint de consulta directa -------------------------------------------

def test_endpoint_diagnostico_responde_el_contrato_3_2(api):
    respuesta = api.post("/prolog/diagnostico", json={
        "servicio": "red", "componente": "red_cableada", "sintomas": ["sin_internet", "vpn_caida"],
        "alcance": "individual", "urgencia": "media", "departamento": "ventas"})
    assert respuesta.status_code == 200
    assert respuesta.json()["causas"][0]["id"] == "cable_desconectado"


def test_endpoint_sintoma_desconocido_es_422_con_la_lista(api):
    respuesta = api.post("/prolog/diagnostico", json={
        "servicio": "red", "sintomas": ["tostadora_rota"], "alcance": "individual",
        "urgencia": "media", "departamento": "ventas"})
    assert respuesta.status_code == 422
    assert respuesta.json()["desconocidos"] == ["tostadora_rota"]


def test_endpoint_prolog_caido_es_503_y_no_500(api):
    from app.config import obtener_configuracion
    from app.main import app

    app.dependency_overrides[obtener_configuracion] = lambda: Configuracion(
        swipl_ejecutable="swipl_inexistente_123")
    respuesta = api.post("/prolog/diagnostico", json={
        "servicio": "red", "sintomas": ["sin_internet"], "alcance": "individual",
        "urgencia": "media", "departamento": "ventas"})
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "no_disponible"
