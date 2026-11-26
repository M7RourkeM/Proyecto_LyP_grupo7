"""Control anti-invencion: verifica que la IA no salga de lo que dio Prolog.

Reglas:
  1. La respuesta tiene las tres claves con el tipo correcto.
  2. pasos_referenciados es subconjunto de los id de pasos de Prolog.
  3. Los pasos referenciados respetan el orden de Prolog.
  4. Cada paso declarado esta escrito de verdad en la guia; sin escalamiento,
     la guia incluye todos los pasos.
  5. Ninguna accion de la lista negra aparece si Prolog no la incluye.
  6. Si el caso se escalo, la guia lo dice y no promete resolucion inmediata.
  7. La guia trata al usuario de usted y, sin escalamiento, numera los pasos.
  8. La nota tecnica no contradice la prioridad ni el escalamiento del motor.
"""

import json
import re
import unicodedata

from pydantic import ValidationError

from app.ia.prompts import SalidaIA

# Acciones que la IA no puede sugerir por su cuenta. Son patrones sobre el
# texto en minusculas y sin tildes, con raices verbales para cubrir el
# infinitivo y el imperativo ("formatear", "formatee", "formateo").
LISTA_NEGRA: tuple[tuple[str, str], ...] = (
    ("formatear", r"\bformate\w*"),
    ("reinstalar", r"\breinstal\w*"),
    ("desinstalar", r"\bdesinstal\w*"),
    ("desactivar el antivirus", r"\b(?:desactiv|deshabilit|apag|quit|detene|deten)\w*\s+"
                                r"(?:\w+\s+){0,2}antivirus"),
    ("editar el registro", r"\bedit\w*\s+(?:\w+\s+){0,2}registro|\bregedit\b"
                           r"|\bregistro de windows\b"),
    ("comprar", r"\bcompr(?:ar|e|en|a|as|ando)\b|\badquir\w*"),
    ("restablecer de fabrica", r"\bfabrica\b"),
    ("comandos de consola", r"\b(?:ipconfig|netsh|cmd|powershell|chkdsk|sfc|regsvr32)\b"),
    ("modificar la BIOS", r"\bbios\b"),
    ("abrir o desarmar el equipo", r"\bdesarm\w*|\babr\w*\s+(?:la\s+)?(?:carcasa|tapa)\b"),
)
PROMESAS_PROHIBIDAS = ("inmediat", "de una vez", "en unos minutos", "en pocos minutos",
                       "ya quedo resuelto", "queda resuelto", "ya esta resuelto")
# Trato de usted: estas formas indican que la guia tutea al usuario.
TUTEO = re.compile(r"\b(te|tu|tus|ti|contigo|puedes|debes|sigue|intenta|reportaste|"
                   r"tienes|revisa|verifica|prueba|contacta|necesitas|quieres|recibes|"
                   r"haces|sabes|escribes|abres|cierras|intentas|usas|ingresas|accedes|"
                   r"envias|logras|recuerdas|olvidaste|cambiaste|reinicia)\b")
# Palabras que no ayudan a reconocer un paso dentro de la guia.
PALABRAS_VACIAS = {"que", "con", "del", "los", "las", "para", "por", "una", "uno", "unos",
                   "este", "esta", "esten", "sea", "son", "sus", "cuando", "como", "otra",
                   "otros", "desde", "hasta", "entre", "sobre", "mismo", "misma", "nuevamente"}
# Proporcion minima de palabras del paso que deben aparecer en la guia.
COBERTURA_MINIMA = 0.5


def normalizar(texto: str) -> str:
    """Minusculas y sin tildes, para comparar frases."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


def interpretar(texto: str) -> SalidaIA:
    """Convierte el texto de la IA en SalidaIA o lanza ValueError con el motivo."""
    try:
        return SalidaIA.model_validate(json.loads(texto))
    except (json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"La respuesta no es el JSON pedido: {error}") from error


def validar(salida: SalidaIA, contexto: dict) -> list[str]:
    """Devuelve la lista de violaciones; vacia si la salida es aceptable."""
    pasos = contexto.get("pasos", [])
    ids = [p["id"] for p in pasos]
    escalar = contexto.get("escalar", False)
    errores = _validar_pasos(salida.pasos_referenciados, ids, escalar)
    errores += _validar_pasos_en_texto(salida, pasos)
    errores += _validar_lista_negra(salida, pasos)
    errores += _validar_escalamiento(salida, contexto)
    errores += _validar_tono(salida.guia_usuario)
    errores += _validar_numeracion(salida.guia_usuario, pasos, escalar)
    errores += _validar_nota(salida.nota_tecnica, contexto)
    return errores


def _validar_pasos(referenciados: list[str], ids: list[str], escalar: bool) -> list[str]:
    errores = [f"El paso '{p}' no existe en el diagnostico; solo se permiten: {', '.join(ids)}"
               for p in referenciados if p not in ids]
    validos = [ids.index(p) for p in referenciados if p in ids]
    if validos != sorted(validos) or len(set(validos)) != len(validos):
        errores.append("Los pasos deben mencionarse una vez y en el orden del diagnostico: "
                       + ", ".join(ids))
    if ids and not escalar:
        faltantes = [i for i in ids if i not in referenciados]
        if faltantes:
            errores.append("Sin escalamiento, la guia debe incluir todos los pasos; faltan: "
                           + ", ".join(faltantes))
    return errores


def _raices(texto: str) -> set[str]:
    """Primeras 4 letras de cada palabra significativa: asi 'Revisar' y 'Revise'
    se reconocen como la misma palabra."""
    palabras = re.findall(r"[a-z]+", normalizar(texto))
    return {p[:4] for p in palabras if len(p) >= 3 and p not in PALABRAS_VACIAS}


def _validar_pasos_en_texto(salida: SalidaIA, pasos: list[dict]) -> list[str]:
    """No basta con declarar un paso en pasos_referenciados: tiene que estar escrito
    en la guia. Se verifica por palabras clave del texto del paso."""
    en_guia = _raices(salida.guia_usuario)
    errores = []
    for paso in pasos:
        if paso["id"] not in salida.pasos_referenciados:
            continue
        claves = _raices(paso["texto"])
        if claves and len(claves & en_guia) / len(claves) < COBERTURA_MINIMA:
            errores.append(f"La guia declara el paso {paso['id']} pero no lo explica; "
                           f"debe indicar: {paso['texto']}")
    return errores


def _validar_tono(guia: str) -> list[str]:
    errores = []
    encontrados = sorted(set(TUTEO.findall(normalizar(guia))))
    if encontrados:
        errores.append(f"La guia debe tratar al usuario de usted; evite: {', '.join(encontrados)}")
    if re.search(r"\bUSTED\b", guia):
        errores.append("No escriba USTED en mayusculas; use verbos como revise o verifique")
    return errores


def _validar_numeracion(guia: str, pasos: list[dict], escalar: bool) -> list[str]:
    """Sin escalamiento y con dos pasos o mas, los pasos deben ir numerados
    1, 2, 3... para que el usuario pueda seguirlos."""
    if escalar or len(pasos) < 2:
        return []
    numeros = [int(n) for n in re.findall(r"(?:^|\s)(\d{1,2})[.)]\s", guia)]
    esperados = list(range(1, len(pasos) + 1))
    encontrados = [n for n in numeros if n in esperados]
    if encontrados[:len(esperados)] != esperados:
        return [f"La guia debe numerar los pasos del 1 al {len(pasos)} en orden "
                "(formato '1. ...', un numero por paso)"]
    return []


def _validar_lista_negra(salida: SalidaIA, pasos: list[dict]) -> list[str]:
    permitido = normalizar(" ".join(p["texto"] for p in pasos))
    generado = normalizar(f"{salida.guia_usuario} {salida.nota_tecnica}")
    return [f"Sugiere '{accion}', que no esta en los pasos del diagnostico"
            for accion, patron in LISTA_NEGRA
            if re.search(patron, generado) and not re.search(patron, permitido)]


def _validar_escalamiento(salida: SalidaIA, contexto: dict) -> list[str]:
    if not contexto.get("escalar"):
        return []
    guia = normalizar(salida.guia_usuario)
    errores = []
    if "escal" not in guia:
        errores.append("El caso fue escalado: la guia debe decirlo")
    errores += [f"El caso fue escalado: la guia no puede prometer resolucion ('{p}')"
                for p in PROMESAS_PROHIBIDAS if p in guia]
    return errores


def _validar_nota(nota: str, contexto: dict) -> list[str]:
    """La nota completa se arma con el resumen de la IA mas los datos del motor
    (ver generador.py); aqui se verifica que el resumen no contradiga al motor."""
    texto = normalizar(nota)
    errores = []
    prioridad = str(contexto.get("prioridad", "")).lower()
    otras = sorted({p for p in re.findall(r"\bp[1-4]\b", texto) if p != prioridad})
    if prioridad and otras:
        errores.append(f"La nota indica la prioridad {', '.join(o.upper() for o in otras)}, "
                       f"pero el motor asigno {prioridad.upper()}")
    if contexto.get("escalar") and "escal" not in texto:
        errores.append("La nota tecnica debe indicar el motivo de escalamiento")
    if not contexto.get("escalar") and re.search(r"\bescal(?:o|ado|ar)\b", texto) and \
            not re.search(r"\bno\b[^.]{0,40}escal", texto):
        errores.append("La nota dice que el caso se escalo, pero el motor lo dejo en primer nivel")
    return errores
