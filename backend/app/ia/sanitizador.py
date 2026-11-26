"""Elimina o enmascara datos sensibles antes de cualquier llamada a la IA.

Se aplica a todo texto que vaya a formar parte de un prompt. El orden de
las reglas importa: primero lo mas especifico (correos, credenciales,
tarjetas) y despues lo mas general (telefonos, IPs, nombres de host),
para que una regla general no rompa un dato que otra regla debia tapar.
"""

import re
from collections.abc import Iterable

# --- Credenciales -------------------------------------------------------
_PALABRAS_CLAVE = r"(?:contrase(?:ñ|n)a|password|passwd|clave|pin|pwd|pass)"
_VALOR = r"(\"[^\"]+\"|'[^']+'|\S+)"
# a) "mi contraseña es X", "la clave del wifi es X", "clave: X", "password=X"
#    (hasta 3 palabras entre la palabra clave y el conector)
_CREDENCIAL_CON_CONECTOR = re.compile(
    rf"\b({_PALABRAS_CLAVE})\b((?:\s+(?!es\b|era\b)[\wáéíóúñ]+){{0,3}}\s*(?:\bes\b|\bera\b|:|=)\s*)"
    + _VALOR, re.IGNORECASE)
# b) "pin 4821", "clave Verano2026": sin conector, solo si el valor tiene un digito.
#    Asi "contraseña expirada" o "clave incorrecta" no se tocan.
_CREDENCIAL_DIRECTA = re.compile(rf"\b({_PALABRAS_CLAVE})\b(\s+)(?=\S*\d)(\S+)",
                                 re.IGNORECASE)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
# token: X, api_key=X, apikey X
_TOKEN_ETIQUETADO = re.compile(
    r"\b(token|api[_\s-]?key|apikey|secret|secreto)(\s*[:=]?\s*)(\S+)", re.IGNORECASE)
# Cadenas largas con prefijos tipicos de llaves (sk-..., ghp_..., AKIA...)
_LLAVE_CONOCIDA = re.compile(r"\b(?:sk|pk|rk|ghp|gho|xox[bp])[-_][A-Za-z0-9_\-]{10,}\b"
                             r"|\bAKIA[0-9A-Z]{16}\b")

# --- Datos personales -----------------------------------------------------
_CORREO = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# 13 a 19 digitos, con espacios o guiones opcionales cada 4
_TARJETA = re.compile(r"\b(?:\d[ \-]?){12,18}\d\b")
# Cedula fisica de Costa Rica: X-XXXX-XXXX, X XXXX XXXX, 0X-0XXX-0XXX, XXXXXXXXX
_CEDULA = re.compile(r"\b0?[1-9][\s\-]?\d{3,4}[\s\-]?\d{3,4}\b")
_CEDULA_CONTEXTO = re.compile(r"\b(c[eé]dula|identificaci[oó]n|dimex)(\s*(?:es|:|#|n[uú]mero)?\s*)"
                              r"([0-9][0-9\s\-]{7,14}[0-9])", re.IGNORECASE)
# Telefono de Costa Rica: 8 digitos que empiezan en 2, 4, 5, 6, 7 u 8, con +506 opcional
_TELEFONO = re.compile(r"(?:\+?506[\s\-]?)?\b[245678]\d{3}[\s\-]?\d{4}\b")

# --- Infraestructura --------------------------------------------------------
_IPV4 = re.compile(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b")
# FQDN internos y nombres de equipo tipo SRV-CORREO-01, pc-fin-023
_HOST_INTERNO = re.compile(r"\b[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.(?:local|lan|corp|internal|intranet|home|test)\b",
                           re.IGNORECASE)
_HOST_EQUIPO = re.compile(r"\b(?=[A-Za-z0-9\-]*\d)[A-Za-z]{2,}(?:-[A-Za-z0-9]+){1,4}\b")
_PRESENTACION = re.compile(r"\b(me llamo|mi nombre es|soy)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
                           r"(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})")


def _es_ip_privada(ip: str) -> bool:
    a, b = (int(x) for x in ip.split(".")[:2])
    return a == 10 or a == 127 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def _luhn_valido(numero: str) -> bool:
    digitos = [int(d) for d in re.sub(r"\D", "", numero)][::-1]
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2)
                for i, d in enumerate(digitos))
    return total % 10 == 0


def _tapar_tarjeta(coincidencia: re.Match) -> str:
    texto = coincidencia.group(0)
    return "[TARJETA]" if _luhn_valido(texto) else texto


def _tapar_ip(coincidencia: re.Match) -> str:
    return "[IP_INTERNA]" if _es_ip_privada(coincidencia.group(0)) else "[IP]"


def _tapar_nombres(texto: str, nombres: Iterable[tuple[str, str]]) -> str:
    """nombres: (nombre completo, rol). Tambien se tapan sus partes de 3+ letras."""
    for nombre, rol in sorted(nombres, key=lambda n: -len(n[0])):
        partes = [nombre] + [p for p in nombre.split() if len(p) >= 3]
        for parte in partes:
            texto = re.sub(rf"\b{re.escape(parte)}\b", rol, texto, flags=re.IGNORECASE)
    return texto


def sanitizar(texto: str, nombres: Iterable[tuple[str, str]] = ()) -> str:
    """Devuelve el texto sin datos sensibles.

    nombres: personas conocidas del caso como (nombre, rol), por ejemplo
    ("Laura Mendez Solis", "el usuario"), para reemplazarlas por su rol.
    """
    if not texto:
        return texto
    texto = _CORREO.sub("[CORREO]", texto)
    texto = _BEARER.sub("Bearer [TOKEN]", texto)
    texto = _LLAVE_CONOCIDA.sub("[TOKEN]", texto)
    texto = _TOKEN_ETIQUETADO.sub(lambda m: f"{m.group(1)}{m.group(2)}[TOKEN]", texto)
    texto = _CREDENCIAL_CON_CONECTOR.sub(lambda m: f"{m.group(1)}{m.group(2)}[CONTRASEÑA]",
                                         texto)
    texto = _CREDENCIAL_DIRECTA.sub(lambda m: f"{m.group(1)}{m.group(2)}[CONTRASEÑA]", texto)
    texto = _CEDULA_CONTEXTO.sub(lambda m: f"{m.group(1)}{m.group(2)}[CEDULA]", texto)
    texto = _TARJETA.sub(_tapar_tarjeta, texto)
    texto = _IPV4.sub(_tapar_ip, texto)
    texto = _HOST_INTERNO.sub("[HOST]", texto)
    texto = _TELEFONO.sub("[TELEFONO]", texto)
    texto = _CEDULA.sub("[CEDULA]", texto)
    texto = _HOST_EQUIPO.sub("[HOST]", texto)
    texto = _tapar_nombres(texto, nombres)
    texto = _PRESENTACION.sub(lambda m: f"{m.group(1)} [NOMBRE]", texto)
    return texto


def sanitizar_estructura(valor, nombres: Iterable[tuple[str, str]] = ()):
    """Aplica sanitizar() a todos los textos de un dict o lista, recursivamente."""
    nombres = list(nombres)
    if isinstance(valor, str):
        return sanitizar(valor, nombres)
    if isinstance(valor, dict):
        return {k: sanitizar_estructura(v, nombres) for k, v in valor.items()}
    if isinstance(valor, list):
        return [sanitizar_estructura(v, nombres) for v in valor]
    return valor
