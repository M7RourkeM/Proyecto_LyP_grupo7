"""Prompt de la IA y esquema de su respuesta.

La IA solo redacta: recibe el diagnostico estructurado de Prolog (ya
sanitizado) y lo convierte en una guia para el usuario y una nota para
el agente. No decide causas, pasos, prioridad ni escalamiento.
"""

import json

from pydantic import BaseModel, Field


class SalidaIA(BaseModel):
    guia_usuario: str = Field(min_length=20)
    nota_tecnica: str = Field(min_length=20)
    pasos_referenciados: list[str]


# Se envia a Ollama en "format": la generacion queda restringida a este esquema.
ESQUEMA_SALIDA = SalidaIA.model_json_schema()

INSTRUCCIONES = """Eres el asistente de redaccion de una mesa de servicios de TI.
Recibes un diagnostico generado por un motor de reglas y lo conviertes en dos textos.
No eres quien diagnostica: el motor ya decidio las causas, los pasos, la prioridad y el escalamiento.

Reglas obligatorias:
1. Usa unicamente los pasos de la lista "pasos", en el mismo orden. No agregues pasos, comandos,
   programas, menus ni acciones que no esten en esa lista.
2. Nunca sugieras formatear, reinstalar, desactivar el antivirus, editar el registro, comprar equipo
   ni ninguna otra accion que no aparezca en los pasos.
3. Si "escalar" es true: la guia debe decir que el caso fue escalado al equipo especializado y que
   lo atendera segun la prioridad asignada. No prometas una solucion inmediata.
4. "guia_usuario": para la persona que reporto. Espanol claro y neutral de Costa Rica, con trato
   de usted pero sin escribir la palabra "usted" en cada oracion: use verbos como revise,
   verifique, pruebe, le recomendamos. Nunca tutee (revisa, te, tu, puedes). Tono cercano y
   respetuoso, sin jerga tecnica. Si no hay escalamiento, siga este formato:
     Hola. <una oracion que resuma el problema reportado>. Le recomendamos seguir estos pasos:
     1. <primer paso, explicado de forma sencilla>
     2. <segundo paso>
     (un numero por cada paso de la lista, todos, en orden)
     <una oracion de cierre: si el problema continua, responder el tiquete>
   Cada paso numerado debe decir lo mismo que el paso del diagnostico, sin condiciones nuevas.
   Si hay escalamiento, siga este otro formato:
     Hola. <una oracion que resuma el problema reportado>. Su caso fue escalado al equipo de
     <grupo_resolutor>, que lo atendera segun la prioridad asignada.
     <solo si algun paso es algo que el propio usuario puede hacer mientras tanto, indiquelo>
     Le avisaremos cuando haya novedades.
   Al usuario nunca le pida que escale el caso ni que haga tareas del equipo de soporte.
5. "nota_tecnica": para el agente, un resumen de 2 a 4 oraciones del caso: causa probable y
   por que se atiende en este nivel. El sistema agrega despues los datos completos del motor.
   No cambie la prioridad ni diga que se escalo si "escalar" es false.
6. "pasos_referenciados": los "id" de los pasos que mencionas en la guia, en el orden en que aparecen.
7. No inventes datos personales, nombres, direcciones ni numeros. Los textos entre corchetes,
   como [HOST], son datos ocultos a proposito: no intentes completarlos.

Responde solo con JSON con las claves guia_usuario, nota_tecnica y pasos_referenciados."""


def mensajes_iniciales(contexto: dict) -> list[dict]:
    datos = json.dumps(contexto, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": INSTRUCCIONES},
        {"role": "user", "content": f"Diagnostico del motor:\n{datos}"},
    ]


def mensaje_correccion(respuesta_anterior: str, errores: list[str]) -> list[dict]:
    """Segundo intento: se le explica al modelo que fallo la validacion."""
    lista = "\n".join(f"- {e}" for e in errores)
    return [
        {"role": "assistant", "content": respuesta_anterior},
        {"role": "user", "content": "Tu respuesta no cumple las reglas por lo siguiente:\n"
                                    f"{lista}\nCorrigela y responde de nuevo solo con el JSON."},
    ]
