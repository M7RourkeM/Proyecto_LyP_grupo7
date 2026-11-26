"""Guia y nota generadas sin IA, a partir del diagnostico de Prolog.

Se usan cuando Ollama no responde o cuando su respuesta no pasa el
validador. Son deterministas: con el mismo diagnostico producen el mismo
texto, y solo contienen lo que dio el motor.
"""

SERVICIOS = {"red": "la conexion de red", "vpn": "la VPN", "correo": "el correo electronico",
             "cuentas": "su cuenta de usuario", "impresoras": "la impresora",
             "sistema_operativo": "su equipo", "apps_negocio": "la aplicacion",
             "nube": "el almacenamiento en la nube", "solicitud": "su solicitud"}


def _horas(valor: float) -> str:
    return f"{valor:g}"


def _duracion(horas: float) -> str:
    """0.25 -> '15 min'; 4 -> '4 h'."""
    return f"{round(horas * 60)} min" if horas < 1 else f"{horas:g} h"


def guia_usuario(contexto: dict) -> str:
    servicio = SERVICIOS.get(contexto.get("categoria", ""), "el servicio reportado")
    lineas = [f"Hola. Recibimos su reporte sobre {servicio} y ya lo analizamos."]
    if contexto["escalar"]:
        lineas.append(
            f"Su caso fue escalado al equipo especializado ({contexto['grupo_resolutor']}), "
            f"que lo atendera segun la prioridad asignada ({contexto['prioridad'].upper()}, "
            f"tiempo objetivo de {_horas(contexto['sla_horas'])} horas habiles). "
            "No necesita hacer nada mas por ahora; le avisaremos cuando haya novedades.")
    elif contexto["pasos"]:
        lineas.append("Le pedimos seguir estos pasos, en este orden:")
        lineas += [f"{p['orden']}. {p['texto']}." for p in contexto["pasos"]]
        lineas.append("Si despues de estos pasos el problema continua, responda a este tiquete "
                      "y un agente de la mesa de ayuda lo atendera.")
    else:
        lineas.append("Un agente de la mesa de ayuda revisara su caso y le contactara.")
    return "\n".join(lineas)


def nota_tecnica(contexto: dict) -> str:
    causas = contexto.get("causas", [])
    lineas = [
        f"Sintomas reportados: {', '.join(contexto.get('sintomas', [])) or 'no indicados'}.",
        "Causa probable: " + (f"{causas[0]['descripcion']} ({causas[0]['id']})."
                              if causas else "sin determinar."),
    ]
    if len(causas) > 1:
        lineas.append("Otras causas posibles: " + "; ".join(c["id"] for c in causas[1:]) + ".")
    descartadas = contexto.get("causas_descartadas", [])
    if descartadas:
        lineas.append("Causas descartadas: " + "; ".join(
            f"{c['id']} ({c['motivo']})" for c in descartadas) + ".")
    if contexto["pasos"]:
        lineas.append("Pasos: " + " ".join(f"{p['orden']}) {p['texto']}." for p in contexto["pasos"]))
    lineas.append(
        f"Prioridad: impacto {contexto['impacto']} x urgencia {contexto['urgencia']} -> "
        f"{contexto['prioridad'].upper()} -> SLA de {_horas(contexto['sla_horas'])} horas habiles "
        f"(primera respuesta en {_duracion(contexto['sla_horas_respuesta'])}).")
    lineas.append(f"Tipo de registro: {contexto['tipo_registro']}.")
    if contexto.get("posible_problema_masivo"):
        lineas.append("Posible problema masivo: hay incidentes abiertos similares en el departamento.")
    if contexto["escalar"]:
        lineas.append(f"Escalamiento: nivel {contexto['nivel']}, grupo "
                      f"{contexto['grupo_resolutor']}. Motivo: {contexto['motivo']}.")
    else:
        lineas.append(f"Atencion en primer nivel. Motivo: {contexto['motivo']}.")
    return "\n".join(lineas)
