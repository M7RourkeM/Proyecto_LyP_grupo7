"""Pruebas del modelo de datos: semilla, claves foraneas, CHECK, unicidad e indices."""

import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.config import obtener_configuracion
from app.models import (Activo, Agente, Departamento, Diagnostico, GrupoResolutor,
                        HistorialTiquete, Tiquete, Usuario)
from scripts.seed import GRUPOS


def contar(sesion, modelo) -> int:
    return sesion.scalar(select(func.count()).select_from(modelo))


def un_tiquete(sesion, **cambios) -> Tiquete:
    usuario = sesion.scalars(select(Usuario)).first()
    valores = dict(usuario_id=usuario.id, departamento_id=usuario.departamento_id,
                   servicio="red", alcance="individual", urgencia_reportada="media")
    valores.update(cambios)
    return Tiquete(**valores)


def un_diagnostico(tiquete_id: int, grupo_id: int) -> Diagnostico:
    return Diagnostico(
        tiquete_id=tiquete_id, causa_principal="cable_desconectado", tipo_registro="incidente",
        impacto="individual", urgencia="media", prioridad="p3", sla_horas_respuesta=4,
        sla_horas_resolucion=16, nivel=1, grupo_resolutor_id=grupo_id,
        motivo="Existe una guia conocida", respuesta_prolog={})


# --- Semilla ----------------------------------------------------------

def test_semilla_carga_las_cantidades_pedidas(sesion_con_datos):
    assert contar(sesion_con_datos, Departamento) == 5
    assert contar(sesion_con_datos, Usuario) == 10
    assert contar(sesion_con_datos, Agente) == 4
    assert contar(sesion_con_datos, Activo) == 15
    assert contar(sesion_con_datos, GrupoResolutor) == 7


def test_semilla_tiene_activos_compartidos_sin_usuario(sesion_con_datos):
    impresoras = sesion_con_datos.scalars(select(Activo).where(Activo.tipo == "impresora")).all()
    assert impresoras and all(a.usuario_id is None for a in impresoras)


@pytest.mark.skipif(shutil.which("swipl") is None, reason="SWI-Prolog no instalado")
def test_grupos_de_la_semilla_coinciden_con_prolog():
    """Los codigos y niveles de la BD deben ser los mismos que usa el motor."""
    kb = obtener_configuracion().ruta_kb()
    objetivo = ("current_prolog_flag(argv, A), last(A, R), load_files(R, [silent(true)]),"
                "forall(grupo_resolutor(G, N, _), format('~w ~w~n', [G, N])), halt(0)")
    salida = subprocess.run(["swipl", "-q", "-g", objetivo, "-t", "halt(1)", "--", str(kb)],
                            capture_output=True, text=True, timeout=10, cwd=kb.parent).stdout
    niveles = {"primer_nivel": 1, "segundo_nivel": 2, "tercer_nivel": 3}
    en_prolog = {g: niveles[n] for g, n in (linea.split() for linea in salida.splitlines())}
    en_semilla = {codigo: nivel for codigo, _, nivel, _ in GRUPOS}
    assert en_semilla == en_prolog


# --- Restricciones ------------------------------------------------------

def test_clave_foranea_inexistente_se_rechaza(sesion):
    sesion.add(Usuario(nombre="X", correo="x@empresa-demo.test", departamento_id=999))
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_estado_de_tiquete_invalido_se_rechaza(sesion_con_datos):
    sesion_con_datos.add(un_tiquete(sesion_con_datos, estado="pendiente"))
    with pytest.raises(IntegrityError):
        sesion_con_datos.commit()


def test_prioridad_invalida_se_rechaza(sesion_con_datos):
    sesion_con_datos.add(un_tiquete(sesion_con_datos, prioridad="p9"))
    with pytest.raises(IntegrityError):
        sesion_con_datos.commit()


def test_tipo_de_activo_invalido_se_rechaza(sesion_con_datos):
    depto = sesion_con_datos.scalars(select(Departamento)).first()
    sesion_con_datos.add(Activo(codigo_inventario="X-1", tipo="tostadora", marca_modelo="X",
                                ubicacion="X", departamento_id=depto.id))
    with pytest.raises(IntegrityError):
        sesion_con_datos.commit()


def test_correo_de_usuario_duplicado_se_rechaza(sesion_con_datos):
    depto = sesion_con_datos.scalars(select(Departamento)).first()
    sesion_con_datos.add(Usuario(nombre="Otra", correo="lmendez@empresa-demo.test",
                                 departamento_id=depto.id))
    with pytest.raises(IntegrityError):
        sesion_con_datos.commit()


def test_un_solo_diagnostico_por_tiquete(sesion_con_datos):
    tiquete = un_tiquete(sesion_con_datos)
    sesion_con_datos.add(tiquete)
    sesion_con_datos.commit()
    grupo = sesion_con_datos.scalars(select(GrupoResolutor)).first()
    sesion_con_datos.add_all([un_diagnostico(tiquete.id, grupo.id),
                              un_diagnostico(tiquete.id, grupo.id)])
    with pytest.raises(IntegrityError):
        sesion_con_datos.commit()


def test_tiquete_valido_se_guarda_con_estado_registrado(sesion_con_datos):
    tiquete = un_tiquete(sesion_con_datos)
    sesion_con_datos.add(tiquete)
    sesion_con_datos.commit()
    assert tiquete.estado == "registrado"
    assert tiquete.creado_en is not None


def test_borrar_tiquete_borra_su_historial(sesion_con_datos):
    tiquete = un_tiquete(sesion_con_datos)
    tiquete.historial.append(HistorialTiquete(estado_nuevo="registrado"))
    sesion_con_datos.add(tiquete)
    sesion_con_datos.commit()
    sesion_con_datos.delete(tiquete)
    sesion_con_datos.commit()
    assert contar(sesion_con_datos, HistorialTiquete) == 0


# --- Indices ------------------------------------------------------------

def test_tiquete_tiene_indices_en_columnas_de_busqueda(motor_prueba):
    indices = inspect(motor_prueba).get_indexes("tiquete")
    columnas = {col for indice in indices for col in indice["column_names"]}
    assert {"estado", "prioridad", "departamento_id", "creado_en"} <= columnas


# --- Fechas ---------------------------------------------------------------

def test_fechas_se_leen_en_utc_con_zona_horaria(sesion_con_datos):
    usuario = sesion_con_datos.scalars(select(Usuario)).first()
    sesion_con_datos.expire_all()  # obliga a releer desde la base
    creado = sesion_con_datos.get(Usuario, usuario.id).creado_en
    assert creado.utcoffset() == timedelta(0)

    # Una hora de Costa Rica (UTC-6) se guarda y se devuelve convertida a UTC.
    hora_cr = datetime(2026, 11, 26, 8, 0, tzinfo=timezone(timedelta(hours=-6)))
    usuario.creado_en = hora_cr
    sesion_con_datos.commit()
    sesion_con_datos.expire_all()
    releido = sesion_con_datos.get(Usuario, usuario.id).creado_en
    assert releido == hora_cr and releido.hour == 14


def test_fecha_sin_zona_horaria_se_rechaza(sesion_con_datos):

    usuario = sesion_con_datos.scalars(select(Usuario)).first()
    usuario.creado_en = datetime(2026, 11, 26, 8, 0)
    with pytest.raises(Exception, match="zona horaria"):
        sesion_con_datos.commit()
