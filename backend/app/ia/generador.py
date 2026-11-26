"""Flujo completo de la IA: sanitizar -> prompt -> Ollama -> validar ->
reintento con el error explicado -> plantilla de respaldo.

El sistema nunca falla por la IA: cualquier problema termina en la
plantilla determinista. El resultado queda en el log y en la base:
ia_ok (primer intento valido), ia_reintento (valido al segundo intento)
o fallback (plantilla).
"""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.ia import plantilla_fallback, prompts, validador
from app.ia.cliente_ollama import ClienteOllama, ErrorIA
from app.ia.sanitizador import sanitizar_estructura

log = logging.getLogger(__name__)


@dataclass
class ResultadoIA:
    guia_usuario: str
    nota_tecnica: str
    resultado: str  # ia_ok | ia_reintento | fallback
    prompt: str  # mensajes enviados en el primer intento, para auditoria
    errores: list[str] = field(default_factory=list)


def generar_textos(contexto: dict, cliente: ClienteOllama | None,
                   nombres: Iterable[tuple[str, str]] = (), tiquete_id: int | None = None
                   ) -> ResultadoIA:
    seguro = sanitizar_estructura(contexto, nombres)
    mensajes = prompts.mensajes_iniciales(seguro)
    prompt = json.dumps(mensajes, ensure_ascii=False, indent=2)
    errores: list[str] = []
    if cliente is not None:
        try:
            resultado = _intentar(cliente, mensajes, seguro, prompt, errores)
            if resultado is not None:
                _registrar(tiquete_id, resultado)
                return resultado
        except ErrorIA as error:
            errores.append(str(error))
    resultado = ResultadoIA(plantilla_fallback.guia_usuario(seguro),
                            plantilla_fallback.nota_tecnica(seguro), "fallback", prompt, errores)
    _registrar(tiquete_id, resultado)
    return resultado


def _intentar(cliente: ClienteOllama, mensajes: list[dict], contexto: dict, prompt: str,
              errores: list[str]) -> ResultadoIA | None:
    """Primer intento y, si no pasa el validador, un reintento con los errores."""
    for etiqueta in ("ia_ok", "ia_reintento"):
        texto = cliente.generar(mensajes, prompts.ESQUEMA_SALIDA)
        try:
            salida = validador.interpretar(texto)
            fallas = validador.validar(salida, contexto)
        except ValueError as error:
            fallas = [str(error)]
        if not fallas:
            return ResultadoIA(salida.guia_usuario, _nota_completa(salida.nota_tecnica, contexto),
                               etiqueta, prompt, errores)
        errores.extend(f"{etiqueta}: {f}" for f in fallas)
        mensajes = mensajes + prompts.mensaje_correccion(texto, fallas)
    return None


def _nota_completa(resumen_ia: str, contexto: dict) -> str:
    """Resumen redactado por la IA + datos exactos del motor. Asi la nota siempre
    trae sintomas, causas, descartes, pasos y la justificacion de la prioridad,
    aunque el modelo omita algo."""
    return (f"{resumen_ia.strip()}\n\nDatos del motor de inferencia:\n"
            f"{plantilla_fallback.nota_tecnica(contexto)}")


def _registrar(tiquete_id: int | None, resultado: ResultadoIA) -> None:
    log.info("IA tiquete=%s resultado=%s errores=%s", tiquete_id, resultado.resultado,
             resultado.errores or "ninguno")
