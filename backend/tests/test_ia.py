"""Pruebas de la IA: validador anti-invencion, reintento, plantilla de respaldo,
cliente de Ollama y que ningun dato sensible llegue al prompt."""

import json
import shutil

import httpx
import pytest

from app.config import Configuracion
from app.ia import plantilla_fallback, validador
from app.ia.cliente_ollama import ClienteOllama, ErrorIA, obtener_cliente_ia
from app.ia.generador import generar_textos
from app.ia.prompts import SalidaIA
from app.main import app

CONTEXTO = {
    "departamento": "ventas", "categoria": "red",
    "sintomas": ["El equipo no logra navegar por Internet", "No se logra establecer la conexion VPN"],
    "causas": [{"id": "cable_desconectado", "descripcion": "El cable de red esta desconectado o danado"},
               {"id": "dhcp_sin_respuesta", "descripcion": "El servidor DHCP no esta asignando direcciones IP"}],
    "causas_descartadas": [{"id": "punto_acceso_wifi", "motivo": "Se descarta porque el reporte indica usa_cable"}],
    "tipo_registro": "incidente", "impacto": "individual", "urgencia": "media", "prioridad": "p3",
    "sla_horas": 16, "sla_horas_respuesta": 4,
    "pasos": [{"orden": 1, "id": "cable_desconectado_1",
               "texto": "Revisar que el cable este conectado al equipo y a la toma de red"},
              {"orden": 2, "id": "cable_desconectado_2", "texto": "Probar con otro cable de red que funcione"},
              {"orden": 3, "id": "cable_desconectado_3", "texto": "Verificar si el equipo recupera la conexion"}],
    "escalar": False, "nivel": 1, "grupo_resolutor": "mesa_ayuda",
    "motivo": "Existe una guia conocida que puede aplicar la mesa de ayuda",
    "motivo_escalamiento": None, "posible_problema_masivo": False, "reglas_aplicadas": [],
}
ESCALADO = {**CONTEXTO, "escalar": True, "nivel": 2, "grupo_resolutor": "redes",
            "motivo": "Hay varios usuarios afectados; posible falla masiva"}

GUIA_BUENA = ("Hola. Para recuperar su conexion: 1. Revise que el cable este bien conectado al "
              "equipo y a la toma de red. 2. Pruebe con otro cable que funcione. 3. Verifique "
              "si el equipo recupera la conexion.")
NOTA_BUENA = ("Sintomas: sin Internet y VPN caida. Causa probable: cable desconectado; tambien "
              "DHCP. Descartado punto de acceso Wi-Fi (usa cable). Prioridad P3: impacto "
              "individual x urgencia media, SLA de 16 horas habiles.")
PASOS = ["cable_desconectado_1", "cable_desconectado_2", "cable_desconectado_3"]


def respuesta(guia=GUIA_BUENA, nota=NOTA_BUENA, pasos=PASOS) -> str:
    return json.dumps({"guia_usuario": guia, "nota_tecnica": nota, "pasos_referenciados": pasos})


class ClienteFalso:
    """Devuelve respuestas predefinidas y guarda lo que se le envio."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas: list[list[dict]] = []

    def generar(self, mensajes, esquema):
        self.llamadas.append(mensajes)
        siguiente = self.respuestas.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente


def errores_de(texto: str, contexto=CONTEXTO) -> list[str]:
    return validador.validar(validador.interpretar(texto), contexto)


# --- Validador ------------------------------------------------------------

def test_respuesta_correcta_no_tiene_errores():
    assert errores_de(respuesta()) == []


def test_paso_inventado_se_rechaza():
    maliciosa = respuesta(pasos=PASOS + ["reiniciar_router_principal"])
    errores = errores_de(maliciosa)
    assert any("reiniciar_router_principal" in e and "no existe" in e for e in errores)


def test_pasos_fuera_de_orden_se_rechazan():
    errores = errores_de(respuesta(pasos=["cable_desconectado_2", "cable_desconectado_1"]))
    assert any("orden" in e for e in errores)


@pytest.mark.parametrize("frase", ["formatee el equipo", "reinstale Windows",
                                   "desactive el antivirus", "apague temporalmente su antivirus",
                                   "edite el registro", "compre un cable nuevo",
                                   "ejecute ipconfig /renew", "restaure de fábrica el equipo",
                                   "entre a la BIOS"])
def test_lista_negra_se_rechaza(frase):
    errores = errores_de(respuesta(guia=GUIA_BUENA + f" Si no funciona, {frase}."))
    assert any("no esta en los pasos" in e for e in errores)


@pytest.mark.parametrize("frase", ["Compruebe que el cable este firme.",
                                   "Registre el mensaje de error.",
                                   "Abra de nuevo la aplicacion."])
def test_palabras_parecidas_a_la_lista_negra_no_se_rechazan(frase):
    assert errores_de(respuesta(guia=GUIA_BUENA + " " + frase)) == []


def test_accion_de_la_lista_negra_se_permite_si_prolog_la_incluye():
    contexto = {**CONTEXTO, "pasos": [{"orden": 1, "id": "controlador_impresora_3",
                "texto": "Solicitar al soporte la reinstalacion del controlador"}]}
    salida = respuesta(guia="Hola. Solicite al soporte la reinstalacion del controlador.",
                       pasos=["controlador_impresora_3"])
    assert errores_de(salida, contexto) == []


def test_caso_escalado_debe_decirlo_y_no_prometer():
    sin_mencion = respuesta(guia="Hola. Estamos revisando su caso con mucho gusto.", pasos=[],
                            nota=NOTA_BUENA + " Escalado a redes.")
    assert any("debe decirlo" in e for e in errores_de(sin_mencion, ESCALADO))
    promesa = respuesta(guia="Su caso fue escalado y quedara resuelto de inmediato.", pasos=[],
                        nota=NOTA_BUENA + " Escalado a redes.")
    assert any("no puede prometer" in e for e in errores_de(promesa, ESCALADO))


def test_nota_no_puede_contradecir_la_prioridad_del_motor():
    errores = errores_de(respuesta(nota="Caso critico, prioridad P1 por la urgencia del usuario."))
    assert any("P1" in e and "P3" in e for e in errores)


def test_nota_no_puede_decir_que_se_escalo_si_el_motor_no_lo_hizo():
    assert any("primer nivel" in e for e in errores_de(
        respuesta(nota="Se escalo el caso al grupo de redes por la falla.")))
    assert errores_de(respuesta(nota="No se recomienda escalado; la mesa de ayuda lo atiende.")) == []


# Salida real de qwen2.5:3b en la primera prueba: anuncia los pasos pero no los da,
# y tutea al usuario. Paso como ia_ok con el validador anterior.
GUIA_REAL_SIN_PASOS = ("Para resolver el problema que reportaste, te proporcionaré los pasos que "
                       "debes seguir. Por favor, sigue estos pasos en el orden indicado para "
                       "intentar solucionar el problema. Si no logras resolverlo, te recomendaré "
                       "que contactes a la mesa de ayuda.")


def test_salida_real_que_anuncia_pasos_sin_darlos_se_rechaza():
    errores = errores_de(respuesta(guia=GUIA_REAL_SIN_PASOS))
    assert sum("no lo explica" in e for e in errores) == 3
    assert any("usted" in e for e in errores)


# Salidas reales de qwen2.5:3b en la segunda prueba: pasaron el validador, pero sin
# numerar los pasos, con "USTED" en mayusculas y con un paso 3 sin sentido.
GUIAS_REALES_SIN_NUMERAR = [
    "USTED revisará que el cable esté conectado al equipo y a la toma de red. USTED probará con "
    "otro cable de red que funcione. USTED verificará si el equipo recupera la conexión. Si el "
    "problema persiste, USTED seguirá los siguientes pasos.",
    "USTED revise que el cable este conectado al equipo y a la toma de red. Si el problema "
    "persiste, pruebe con otro cable de red que funcione. Si el equipo recupera la conexión, "
    "verifique si el equipo recupera la conexión.",
]


@pytest.mark.parametrize("guia", GUIAS_REALES_SIN_NUMERAR, ids=["futuro", "condicional"])
def test_salidas_reales_sin_numerar_se_rechazan(guia):
    errores = errores_de(respuesta(guia=guia))
    assert any("numerar los pasos" in e for e in errores)
    assert any("mayusculas" in e for e in errores)


def test_tuteo_real_del_caso_escalado_se_rechaza():
    guia = ("Hola. El problema es que no recibes mensajes por correo. Su caso fue escalado al "
            "equipo de infraestructura, que lo atendera segun la prioridad asignada.")
    salida = respuesta(guia=guia, pasos=[], nota="Escalado a infraestructura por varios usuarios.")
    assert any("recibes" in e for e in errores_de(salida, ESCALADO))


def test_numeracion_incompleta_o_desordenada_se_rechaza():
    desordenada = GUIA_BUENA.replace("1. Revise", "2. Revise").replace("2. Pruebe", "1. Pruebe")
    assert any("numerar" in e for e in errores_de(respuesta(guia=desordenada)))


def test_caso_escalado_no_exige_numeracion():
    guia = "Hola. Su caso fue escalado al equipo de redes, que lo atendera segun la prioridad."
    salida = respuesta(guia=guia, pasos=[], nota="Escalado a redes por varios usuarios.")
    assert errores_de(salida, ESCALADO) == []


def test_sin_escalamiento_deben_estar_todos_los_pasos():
    errores = errores_de(respuesta(pasos=["cable_desconectado_1", "cable_desconectado_2"]))
    assert any("faltan: cable_desconectado_3" in e for e in errores)


def test_paso_redactado_con_otras_palabras_se_reconoce():
    guia = ("Hola. 1. Revise que el cable este bien conectado a su equipo y a la toma de red. "
            "2. Pruebe con otro cable de red que si funcione. "
            "3. Verifique si su equipo recupera la conexion.")
    assert errores_de(respuesta(guia=guia)) == []


def test_json_mal_formado_se_reporta():
    with pytest.raises(ValueError):
        validador.interpretar("Claro, aqui esta la guia: ...")


# --- Plantilla de respaldo ---------------------------------------------------

@pytest.mark.parametrize("contexto", [CONTEXTO, ESCALADO], ids=["primer_nivel", "escalado"])
def test_la_plantilla_cumple_las_mismas_reglas_que_la_ia(contexto):
    salida = SalidaIA(guia_usuario=plantilla_fallback.guia_usuario(contexto),
                      nota_tecnica=plantilla_fallback.nota_tecnica(contexto),
                      pasos_referenciados=[] if contexto["escalar"] else PASOS)
    assert validador.validar(salida, contexto) == []


# --- Flujo completo: intento, reintento y respaldo ---------------------------

def test_primer_intento_valido_es_ia_ok():
    resultado = generar_textos(CONTEXTO, ClienteFalso(respuesta()))
    assert resultado.resultado == "ia_ok" and resultado.guia_usuario == GUIA_BUENA


def test_tiempo_de_respuesta_menor_a_una_hora_se_muestra_en_minutos():
    nota = plantilla_fallback.nota_tecnica({**ESCALADO, "sla_horas_respuesta": 0.25})
    assert "primera respuesta en 15 min" in nota


def test_nota_final_es_el_resumen_de_la_ia_mas_los_datos_del_motor():
    nota = generar_textos(CONTEXTO, ClienteFalso(respuesta())).nota_tecnica
    resumen, datos = nota.split("Datos del motor de inferencia:")
    assert resumen.strip() == NOTA_BUENA
    for esperado in ["Sintomas reportados", "Causas descartadas: punto_acceso_wifi",
                     "impacto individual x urgencia media -> P3 -> SLA de 16 horas", "Pasos: 1)"]:
        assert esperado in datos, esperado


def test_reintento_le_explica_el_error_al_modelo():
    cliente = ClienteFalso(respuesta(pasos=PASOS + ["paso_inventado"]), respuesta())
    resultado = generar_textos(CONTEXTO, cliente)
    assert resultado.resultado == "ia_reintento"
    correccion = cliente.llamadas[1][-1]["content"]
    assert "paso_inventado" in correccion and "no existe" in correccion


def test_respuesta_maliciosa_dos_veces_termina_en_plantilla():
    maliciosa = respuesta(pasos=PASOS + ["paso_inventado"])
    resultado = generar_textos(CONTEXTO, ClienteFalso(maliciosa, maliciosa))
    assert resultado.resultado == "fallback"
    assert "paso_inventado" not in resultado.guia_usuario
    assert resultado.guia_usuario.startswith("Hola. Recibimos su reporte")
    assert len(resultado.errores) >= 2


def test_ia_que_falla_termina_en_plantilla_sin_excepcion():
    resultado = generar_textos(CONTEXTO, ClienteFalso(ErrorIA("Ollama no respondio")))
    assert resultado.resultado == "fallback"


def test_sin_cliente_se_usa_la_plantilla():
    assert generar_textos(CONTEXTO, None).resultado == "fallback"


def test_dato_sensible_en_el_contexto_no_llega_al_prompt():
    contexto = {**CONTEXTO, "motivo": "Contactar a Laura Mendez Solis al 8800-0001"}
    cliente = ClienteFalso(respuesta())
    resultado = generar_textos(contexto, cliente, [("Laura Mendez Solis", "el usuario")])
    enviado = json.dumps(cliente.llamadas[0], ensure_ascii=False)
    assert "Laura" not in enviado and "8800-0001" not in enviado
    assert "Laura" not in resultado.prompt


# --- Cliente de Ollama ---------------------------------------------------------

def config_ollama(**extra) -> Configuracion:
    return Configuracion(ollama_url="http://ollama.local", ollama_timeout_s=2, **extra)


def test_cliente_envia_el_formato_de_la_api_de_ollama():
    capturado = {}

    def responder(peticion: httpx.Request) -> httpx.Response:
        capturado.update(ruta=peticion.url.path, cuerpo=json.loads(peticion.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "{}"}})

    ClienteOllama(config_ollama(), httpx.MockTransport(responder)).generar(
        [{"role": "user", "content": "x"}], {"type": "object"})
    assert capturado["ruta"] == "/api/chat"
    assert capturado["cuerpo"]["stream"] is False
    assert capturado["cuerpo"]["model"] == "qwen2.5:3b"
    assert capturado["cuerpo"]["format"] == {"type": "object"}
    assert capturado["cuerpo"]["keep_alive"] == "30m"


def test_precarga_envia_una_consulta_vacia_y_no_falla_si_ollama_no_esta():
    capturado = {}

    def responder(peticion):
        capturado.update(json.loads(peticion.content))
        return httpx.Response(200, json={})

    ClienteOllama(config_ollama(), httpx.MockTransport(responder)).precargar()
    assert capturado == {"model": "qwen2.5:3b", "keep_alive": "30m"}

    def apagado(peticion):
        raise httpx.ConnectError("conexion rechazada")

    ClienteOllama(config_ollama(), httpx.MockTransport(apagado)).precargar()  # no lanza


@pytest.mark.parametrize("falla", [
    httpx.ConnectError("conexion rechazada"), httpx.ReadTimeout("tiempo agotado")],
    ids=["ollama_apagado", "timeout"])
def test_cliente_reintenta_una_vez_y_luego_falla(falla):
    intentos = []

    def responder(peticion):
        intentos.append(1)
        raise falla

    cliente = ClienteOllama(config_ollama(), httpx.MockTransport(responder))
    with pytest.raises(ErrorIA):
        cliente.generar([], {})
    assert len(intentos) == 2


def test_error_500_de_ollama_tambien_se_reintenta():
    cliente = ClienteOllama(config_ollama(), httpx.MockTransport(lambda p: httpx.Response(500)))
    with pytest.raises(ErrorIA):
        cliente.generar([], {})


# --- Integracion con la API ------------------------------------------------------

requiere_swipl = pytest.mark.skipif(shutil.which("swipl") is None, reason="SWI-Prolog no instalado")
TIQUETE = {"usuario_id": 1, "activo_id": 1, "servicio": "red", "componente": "red_cableada",
           "sintomas": ["sin_internet", "vpn_caida"], "alcance": "individual", "urgencia": "media"}


@requiere_swipl
def test_ollama_apagado_responde_con_plantilla_y_sin_error_500(api):
    apagado = ClienteOllama(Configuracion(ollama_url="http://127.0.0.1:9", ollama_timeout_s=2))
    app.dependency_overrides[obtener_cliente_ia] = lambda: apagado
    respuesta_api = api.post("/tiquetes", json=TIQUETE)
    assert respuesta_api.status_code == 201
    diagnostico = respuesta_api.json()["tiquete"]["diagnostico"]
    assert diagnostico["resultado_ia"] == "fallback"
    assert "Revisar que el cable" in diagnostico["guia_usuario"]


@requiere_swipl
def test_guia_de_la_ia_se_guarda_en_el_diagnostico(api):
    app.dependency_overrides[obtener_cliente_ia] = lambda: ClienteFalso(respuesta())
    diagnostico = api.post("/tiquetes", json=TIQUETE).json()["tiquete"]["diagnostico"]
    assert diagnostico["resultado_ia"] == "ia_ok"
    assert diagnostico["guia_usuario"] == GUIA_BUENA


@requiere_swipl
def test_escenario_6_contrasena_y_cedula_no_llegan_al_prompt(api):
    """El texto libre trae una contrasena y una cedula: el prompt no debe tener ninguna."""
    cliente = ClienteFalso(respuesta())
    app.dependency_overrides[obtener_cliente_ia] = lambda: cliente
    descripcion = ("Soy Laura Mendez Solis, cedula 1-1111-0001. Mi contraseña es Verano2026 "
                   "y no puedo entrar a la VPN.")
    tiquete = api.post("/tiquetes", json={**TIQUETE, "descripcion": descripcion}).json()["tiquete"]
    prompt = api.get(f"/tiquetes/{tiquete['id']}/ia").json()["prompt_ia"]
    enviado = json.dumps(cliente.llamadas[0], ensure_ascii=False)
    for sensible in ["Verano2026", "1-1111-0001", "Laura", "lmendez"]:
        assert sensible not in prompt, sensible
        assert sensible not in enviado, sensible
    assert "sin_internet" in prompt or "navegar por Internet" in prompt
