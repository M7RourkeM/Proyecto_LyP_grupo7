"""Orquestacion al crear un tiquete: correlacion -> Prolog -> IA -> guardar.

Este modulo no decide nada del diagnostico: arma la entrada, llama al
motor, guarda lo que devuelve y le pide a la IA que lo redacte. La IA
recibe solo el diagnostico estructurado, nunca el texto libre del usuario.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Configuracion
from app.ia.cliente_ollama import ClienteOllama
from app.ia.generador import generar_textos
from app.models import (Activo, Agente, DatoReporte, Departamento, Diagnostico,
                        GrupoResolutor, PasoDiagnostico, Retroalimentacion, Tiquete, Usuario)
from app.prolog.adaptador_base import AdaptadorProlog, EntradaInvalida, ErrorProlog
from app.schemas.prolog import (CatalogoProlog, DiagnosticoProlog, EntradaDiagnostico,
                                ResultadoPrevio)
from app.schemas.tiquetes import TiqueteCrear
from app.services import ciclo_vida, correlacion

log = logging.getLogger(__name__)
AVISO_SIN_DIAGNOSTICO = ("El diagnostico automatico no esta disponible; el tiquete quedo "
                         "registrado para la mesa de ayuda. Puede reintentarse con "
                         "POST /tiquetes/{id}/diagnostico.")
_catalogos: dict[str, CatalogoProlog] = {}


class ReferenciaInvalida(Exception):
    """El cuerpo referencia un registro inexistente o inactivo (422)."""


class DiagnosticoExistente(Exception):
    """El tiquete ya tiene diagnostico (409)."""


def crear_tiquete(sesion: Session, datos: TiqueteCrear, adaptador: AdaptadorProlog,
                  config: Configuracion, cliente_ia: ClienteOllama | None
                  ) -> tuple[Tiquete, str | None]:
    """Crea el tiquete y lo diagnostica. Devuelve (tiquete, aviso).

    Si el motor rechaza la entrada (sintoma desconocido) no se crea nada.
    Si el motor no esta disponible, el tiquete se crea sin diagnostico.
    """
    usuario = _validar_referencias(sesion, datos)
    tiquete = Tiquete(usuario_id=usuario.id, activo_id=datos.activo_id,
                      departamento_id=usuario.departamento_id, servicio=datos.servicio,
                      componente=datos.componente, descripcion=datos.descripcion,
                      alcance=datos.alcance, urgencia_reportada=datos.urgencia,
                      pasos_ya_aplicados=len(datos.pasos_ya_aplicados),
                      sospecha_seguridad=datos.sospecha_seguridad)
    tipos = _tipos_de_datos(adaptador, datos.sintomas)
    tiquete.datos_reporte = [DatoReporte(codigo=c, tipo=tipos.get(c, "sintoma"))
                             for c in dict.fromkeys(datos.sintomas)]
    ciclo_vida.registrar_inicio(tiquete, "Tiquete registrado por el usuario")
    sesion.add(tiquete)
    sesion.flush()  # asigna el id sin confirmar la transaccion

    aviso = _diagnosticar(sesion, tiquete, adaptador, config, cliente_ia,
                          datos.pasos_ya_aplicados)
    sesion.commit()
    return tiquete, aviso


def reintentar_diagnostico(sesion: Session, tiquete: Tiquete, adaptador: AdaptadorProlog,
                           config: Configuracion, cliente_ia: ClienteOllama | None) -> str | None:
    if tiquete.diagnostico is not None:
        raise DiagnosticoExistente(f"El tiquete {tiquete.id} ya tiene diagnostico")
    if tiquete.estado not in correlacion.ESTADOS_ABIERTOS:
        raise ciclo_vida.TransicionInvalida(f"El tiquete esta {tiquete.estado}; no se diagnostica")
    # El motor solo usa la cantidad de pasos aplicados.
    pasos = [f"paso_{n}" for n in range(tiquete.pasos_ya_aplicados)]
    aviso = _diagnosticar(sesion, tiquete, adaptador, config, cliente_ia, pasos)
    sesion.commit()
    return aviso


def _validar_referencias(sesion: Session, datos: TiqueteCrear) -> Usuario:
    usuario = sesion.get(Usuario, datos.usuario_id)
    if usuario is None:
        raise ReferenciaInvalida(f"usuario_id: no existe un usuario con id {datos.usuario_id}")
    if not usuario.activo:
        raise ReferenciaInvalida(f"El usuario {datos.usuario_id} esta desactivado")
    if datos.activo_id is not None and sesion.get(Activo, datos.activo_id) is None:
        raise ReferenciaInvalida(f"activo_id: no existe un activo con id {datos.activo_id}")
    return usuario


def _diagnosticar(sesion: Session, tiquete: Tiquete, adaptador: AdaptadorProlog,
                  config: Configuracion, cliente_ia: ClienteOllama | None,
                  pasos_aplicados: list[str]) -> str | None:
    """Consulta al motor y aplica el resultado. Devuelve un aviso si no hubo diagnostico."""
    departamento = sesion.get(Departamento, tiquete.departamento_id).codigo
    sintomas = [d.codigo for d in tiquete.datos_reporte]
    entrada = EntradaDiagnostico(
        tiquete_id=tiquete.id, servicio=tiquete.servicio, componente=tiquete.componente,
        sintomas=sintomas, alcance=tiquete.alcance, urgencia=tiquete.urgencia_reportada,
        departamento=departamento, pasos_ya_aplicados=pasos_aplicados,
        sospecha_seguridad=tiquete.sospecha_seguridad)
    similares = correlacion.incidentes_similares(
        sesion, config, tiquete.departamento_id, departamento, tiquete.servicio, sintomas,
        excluir_id=tiquete.id)
    try:
        resultado = adaptador.diagnosticar(entrada, similares, _resultados_previos(sesion))
        grupo = _grupo_del_diagnostico(sesion, resultado)
    except EntradaInvalida:
        sesion.rollback()
        raise
    except ErrorProlog as error:
        # El reporte no se pierde: queda registrado para la mesa de ayuda.
        log.warning("Tiquete %s sin diagnostico: %s", tiquete.id, error.detalle)
        _asignar_mesa_de_ayuda(sesion, tiquete)
        return AVISO_SIN_DIAGNOSTICO.replace("{id}", str(tiquete.id))
    _guardar_diagnostico(sesion, tiquete, resultado, grupo)
    _redactar_con_ia(sesion, tiquete, resultado, departamento, adaptador, cliente_ia)
    return None


def _redactar_con_ia(sesion: Session, tiquete: Tiquete, resultado: DiagnosticoProlog,
                     departamento: str, adaptador: AdaptadorProlog,
                     cliente_ia: ClienteOllama | None) -> None:
    """La IA recibe solo datos tecnicos: nada del texto libre, ni nombres,
    correos o identificaciones. Igual se sanitiza todo como segunda barrera."""
    contexto = resultado.model_dump(exclude={"incidentes_relacionados"})
    contexto["departamento"] = departamento
    contexto["sintomas"] = _descripciones(adaptador, [d.codigo for d in tiquete.datos_reporte])
    usuario = sesion.get(Usuario, tiquete.usuario_id)
    nombres = [(usuario.nombre, "el usuario")]
    nombres += [(nombre, "el agente") for nombre in sesion.scalars(select(Agente.nombre))]
    textos = generar_textos(contexto, cliente_ia, nombres, tiquete.id)
    diagnostico = tiquete.diagnostico
    diagnostico.guia_usuario = textos.guia_usuario
    diagnostico.nota_tecnica = textos.nota_tecnica
    diagnostico.resultado_ia = textos.resultado
    diagnostico.prompt_ia = textos.prompt


def _grupo_del_diagnostico(sesion: Session, resultado: DiagnosticoProlog) -> GrupoResolutor:
    grupo = sesion.scalar(select(GrupoResolutor).where(
        GrupoResolutor.codigo == resultado.grupo_resolutor))
    if grupo is None:
        raise ErrorProlog(f"El motor asigno el grupo {resultado.grupo_resolutor}, "
                          "que no existe en la base de datos")
    return grupo


def _guardar_diagnostico(sesion: Session, tiquete: Tiquete, resultado: DiagnosticoProlog,
                         grupo: GrupoResolutor) -> None:
    tiquete.diagnostico = Diagnostico(
        causa_principal=resultado.causas[0].id if resultado.causas else "sin_determinar",
        otras_causas=[c.id for c in resultado.causas[1:]],
        causas_descartadas=[c.model_dump() for c in resultado.causas_descartadas],
        tipo_registro=resultado.tipo_registro, impacto=resultado.impacto,
        urgencia=resultado.urgencia, prioridad=resultado.prioridad,
        sla_horas_respuesta=resultado.sla_horas_respuesta,
        sla_horas_resolucion=resultado.sla_horas, nivel=resultado.nivel,
        grupo_resolutor_id=grupo.id, motivo=resultado.motivo,
        posible_problema_masivo=resultado.posible_problema_masivo,
        incidentes_relacionados=resultado.incidentes_relacionados,
        reglas_aplicadas=resultado.reglas_aplicadas,
        respuesta_prolog=resultado.model_dump(),
        pasos=[PasoDiagnostico(orden=p.orden, codigo=p.id, texto=p.texto)
               for p in resultado.pasos])
    tiquete.categoria = resultado.categoria
    tiquete.tipo_registro = resultado.tipo_registro
    tiquete.prioridad = resultado.prioridad
    tiquete.nivel = resultado.nivel
    tiquete.grupo_resolutor_id = grupo.id
    tiquete.sla_horas_resolucion = resultado.sla_horas
    if resultado.escalar and tiquete.estado in ("registrado", "en_atencion"):
        ciclo_vida.transicionar(sesion, tiquete, "escalado",
                                comentario=f"Escalado por el motor: {resultado.motivo}")


def _asignar_mesa_de_ayuda(sesion: Session, tiquete: Tiquete) -> None:
    if tiquete.grupo_resolutor_id is None:
        mesa = sesion.scalar(select(GrupoResolutor).where(GrupoResolutor.nivel == 1))
        tiquete.grupo_resolutor_id = mesa.id if mesa else None
        tiquete.nivel = 1


def _catalogo(adaptador: AdaptadorProlog) -> CatalogoProlog | None:
    """Catalogo del motor, consultado una vez por base de conocimiento."""
    clave = str(adaptador.ruta_kb)
    if clave not in _catalogos:
        try:
            _catalogos[clave] = adaptador.catalogo()
        except ErrorProlog:
            return None
    return _catalogos[clave]


def _tipos_de_datos(adaptador: AdaptadorProlog, codigos: list[str]) -> dict[str, str]:
    """Clasifica cada codigo como sintoma, contexto, evidencia o peticion segun el
    catalogo del motor. Si el motor no responde, todos se guardan como sintoma."""
    catalogo = _catalogo(adaptador)
    if catalogo is None:
        return {}
    return {c: tipo for c in codigos if (tipo := catalogo.tipo_de(c))}


def _descripciones(adaptador: AdaptadorProlog, codigos: list[str]) -> list[str]:
    """Descripcion de cada dato del reporte segun el motor (o el codigo si no hay)."""
    catalogo = _catalogo(adaptador)
    items = {} if catalogo is None else {
        i.codigo: i.descripcion for grupo in (catalogo.sintomas, catalogo.peticiones,
                                              catalogo.contextos, catalogo.evidencias)
        for i in grupo}
    return [items.get(c, c) for c in codigos]


def _resultados_previos(sesion: Session) -> list[ResultadoPrevio]:
    """Retroalimentacion historica (si funciono la solucion de cada causa)."""
    filas = sesion.execute(
        select(Diagnostico.causa_principal, Retroalimentacion.funciono)
        .join(Retroalimentacion, Retroalimentacion.tiquete_id == Diagnostico.tiquete_id)
        .where(Diagnostico.causa_principal != "sin_determinar"))
    return [ResultadoPrevio(causa=causa, funciono=funciono) for causa, funciono in filas]
