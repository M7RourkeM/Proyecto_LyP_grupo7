"""Valores permitidos de los campos enumerados.

Se usan en las restricciones CHECK de la base de datos y, en fases
posteriores, en los esquemas Pydantic, para que ambos coincidan.
Los valores de diagnostico coinciden con los atomos del motor Prolog.
"""

ESTADOS_TIQUETE = ("registrado", "en_atencion", "escalado", "resuelto", "cerrado")
ALCANCES = ("individual", "departamento", "organizacion")
URGENCIAS = ("baja", "media", "alta")
PRIORIDADES = ("p1", "p2", "p3", "p4")
TIPOS_REGISTRO = ("incidente", "solicitud_servicio", "problema")
NIVELES = (1, 2, 3)
RESULTADOS_IA = ("ia_ok", "ia_reintento", "fallback")
TIPOS_ACTIVO = ("laptop", "escritorio", "impresora", "telefono", "servidor", "otro")
TIPOS_DATO_REPORTE = ("sintoma", "contexto", "evidencia", "peticion")

# Equivalencia entre el nivel textual de Prolog y el nivel numerico.
NIVEL_POR_ATOMO = {"primer_nivel": 1, "segundo_nivel": 2, "tercer_nivel": 3}


def check_en(columna: str, valores: tuple) -> str:
    """Construye la expresion SQL de un CHECK ... IN (...)."""
    lista = ", ".join(str(v) if isinstance(v, int) else f"'{v}'" for v in valores)
    return f"{columna} IN ({lista})"
