"""Pruebas del sanitizador: ningun dato sensible debe llegar a la IA."""

import pytest

from app.ia.sanitizador import sanitizar, sanitizar_estructura

NOMBRES = [("Laura Mendez Solis", "el usuario"), ("Daniela Soto Arias", "el agente")]

# (texto original, lo que NO debe quedar, marcador esperado)
CASOS = [
    ("Mi contraseña es Hola1234! y no entra", "Hola1234!", "[CONTRASEÑA]"),
    ("la clave: Verano2026", "Verano2026", "[CONTRASEÑA]"),
    ("password=Sup3rS3cr3t", "Sup3rS3cr3t", "[CONTRASEÑA]"),
    ("mi contrasena nueva es 'casa azul 99'", "casa azul 99", "[CONTRASEÑA]"),
    ("el pin 4821 del celular", "4821", "[CONTRASEÑA]"),
    ("la clave del wifi es casa123", "casa123", "[CONTRASEÑA]"),
    ("token: ghp_A1b2C3d4E5f6G7h8I9j0", "ghp_A1b2C3d4E5f6G7h8I9j0", "[TOKEN]"),
    ("uso la llave sk-proj-abc123DEF456ghi789", "sk-proj-abc123DEF456ghi789", "[TOKEN]"),
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def", "eyJhbGciOiJIUzI1NiJ9", "[TOKEN]"),
    ("escribame a laura.mendez@empresa.co.cr", "laura.mendez@empresa.co.cr", "[CORREO]"),
    ("mi cedula es 1-1234-0567", "1-1234-0567", "[CEDULA]"),
    ("cédula 112340567 por favor", "112340567", "[CEDULA]"),
    ("identificacion: 1 1234 0567", "1 1234 0567", "[CEDULA]"),
    ("ced 01-1234-0567", "01-1234-0567", "[CEDULA]"),
    ("llamarme al 8888-1234", "8888-1234", "[TELEFONO]"),
    ("o al +506 2222 3344", "2222 3344", "[TELEFONO]"),
    ("pagué con 4111 1111 1111 1111", "4111 1111 1111 1111", "[TARJETA]"),
    ("tarjeta 5500-0000-0000-0004", "5500-0000-0000-0004", "[TARJETA]"),
    ("no hace ping a 192.168.10.25", "192.168.10.25", "[IP_INTERNA]"),
    ("la puerta de enlace es 10.0.0.1", "10.0.0.1", "[IP_INTERNA]"),
    ("el servidor mail.empresa.local no responde", "mail.empresa.local", "[HOST]"),
    ("no conecta a SRV-CORREO-01", "SRV-CORREO-01", "[HOST]"),
    ("Hola, me llamo Pedro Picado y no tengo red", "Pedro Picado", "[NOMBRE]"),
]


@pytest.mark.parametrize("texto,sensible,marcador", CASOS, ids=[c[2] + "-" + str(i)
                                                               for i, c in enumerate(CASOS)])
def test_dato_sensible_se_elimina(texto, sensible, marcador):
    resultado = sanitizar(texto)
    assert sensible not in resultado
    assert marcador in resultado


def test_nombres_conocidos_se_reemplazan_por_su_rol():
    texto = "Laura Mendez Solis reporta el caso; Daniela lo atendio. Mendez insiste."
    resultado = sanitizar(texto, NOMBRES)
    assert "Laura" not in resultado and "Mendez" not in resultado and "Daniela" not in resultado
    assert resultado.startswith("el usuario reporta") and "el agente lo atendio" in resultado


def test_ip_publica_tambien_se_enmascara_pero_distinta():
    assert sanitizar("ping a 8.8.8.8") == "ping a [IP]"


def test_varios_datos_en_un_mismo_texto():
    texto = ("Soy Laura Mendez Solis, cedula 1-1111-0001, correo lmendez@empresa-demo.test, "
             "tel 8800-0001. Mi contraseña es Clave123 y la PC es PC-FIN-023 (10.1.2.3).")
    resultado = sanitizar(texto, NOMBRES)
    for sensible in ["Laura", "1-1111-0001", "lmendez@", "8800-0001", "Clave123",
                     "PC-FIN-023", "10.1.2.3"]:
        assert sensible not in resultado, sensible


# --- Lo que NO se debe tocar ---------------------------------------------------

@pytest.mark.parametrize("texto", [
    "El equipo no logra navegar por Internet",
    "Reiniciar el equipo y verificar el cable de red",
    "Prioridad P3 con SLA de 16 horas habiles",
    "Windows 11 con 2 monitores",
    "Renovar la direccion IP desde la configuracion de red",
    "Se aplicaron 4 pasos sin resolver el caso",
    "La contraseña expirada no permite entrar",
    "Hice ping al servidor y no responde",
    "Cerrar la aplicacion y volver a abrirla",
])
def test_texto_tecnico_sin_datos_sensibles_no_cambia(texto):
    assert sanitizar(texto) == texto


def test_numero_que_no_pasa_luhn_no_se_marca_como_tarjeta():
    assert "[TARJETA]" not in sanitizar("pedido 1234 5678 9012 3456")


def test_estructuras_anidadas_se_sanitizan_completas():
    datos = {"pasos": [{"texto": "Llamar al 8800-0001"}], "nota": "clave: abc123", "n": 3}
    resultado = sanitizar_estructura(datos)
    assert resultado == {"pasos": [{"texto": "Llamar al [TELEFONO]"}],
                         "nota": "clave: [CONTRASEÑA]", "n": 3}


def test_texto_vacio_o_nulo():
    assert sanitizar("") == ""
    assert sanitizar(None) is None


@pytest.mark.skipif(__import__("shutil").which("swipl") is None, reason="SWI-Prolog no instalado")
def test_ningun_texto_de_la_base_de_conocimiento_se_altera():
    """El diagnostico de Prolog tambien pasa por el sanitizador: si alterara un
    paso, la IA recibiria un paso distinto al que dio el motor."""
    import subprocess

    from app.config import obtener_configuracion

    kb = obtener_configuracion().ruta_kb()
    objetivo = ("current_prolog_flag(argv, A), last(A, R), load_files(R, [silent(true)]),"
                "forall((solucion(_,_,T) ; causa(_,T) ; sintoma(_,_,T) ; grupo_resolutor(_,_,T)"
                " ; evidencia(_,T) ; contexto(_,_,T)), (write(T), nl)), halt(0)")
    salida = subprocess.run(["swipl", "-q", "-g", objetivo, "-t", "halt(1)", "--", str(kb)],
                            capture_output=True, text=True, encoding="utf-8", timeout=20,
                            cwd=kb.parent).stdout
    textos = [t for t in salida.splitlines() if t]
    assert len(textos) > 50
    assert [t for t in textos if sanitizar(t) != t] == []
