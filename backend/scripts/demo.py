"""Recorrido de los 7 escenarios de validacion, de punta a punta.

Usa la API real (FastAPI en el mismo proceso), el motor Prolog y Ollama,
sobre una base de datos temporal en memoria: no modifica mesa_servicios.db
ni necesita el servidor levantado. Cada escenario compara el resultado con
lo que pide el enunciado y lo marca como [OK] o [FALLA].

Uso (desde la carpeta backend):
    .venv\\Scripts\\python -m scripts.demo            con IA (Ollama encendido)
    .venv\\Scripts\\python -m scripts.demo --sin-ia   solo plantillas, mas rapido
"""

import argparse
import json
import logging
import sys
import time
import warnings
from collections.abc import Callable

# Aviso interno de Starlette sobre su cliente de pruebas: no afecta a la demo.
warnings.filterwarnings("ignore", message=".*httpx.*")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.config import Configuracion, obtener_configuracion
from app.database import Base, crear_motor, obtener_sesion
from app.ia.cliente_ollama import ClienteOllama, obtener_cliente_ia
from app.main import app
from scripts.seed import cargar_datos

# En la semilla: usuarios 1-2 Finanzas, 3-4 Ventas, 5-6 Recursos Humanos;
# activo 3 es la laptop del usuario 3. Grupos: 2 redes, 3 cuentas y accesos,
# 4 soporte de equipos, 6 infraestructura.
RED = {"usuario_id": 3, "activo_id": 3, "servicio": "red", "componente": "red_cableada",
       "sintomas": ["sin_internet", "vpn_caida"], "alcance": "individual", "urgencia": "media"}


class Demo:
    def __init__(self, cliente: TestClient, mostrar_textos: bool):
        self.api = cliente
        self.mostrar_textos = mostrar_textos
        self.resultados: list[tuple[str, bool]] = []

    def crear(self, **datos) -> dict:
        respuesta = self.api.post("/tiquetes", json=datos)
        if respuesta.status_code != 201:
            raise RuntimeError(f"POST /tiquetes respondio {respuesta.status_code}: {respuesta.text}")
        return respuesta.json()

    def escenario(self, numero: int, titulo: str, ejecutar: Callable[[], list[tuple[str, bool]]]):
        print(f"\n{'=' * 78}\nESCENARIO {numero}: {titulo}\n{'=' * 78}")
        inicio = time.perf_counter()
        try:
            verificaciones = ejecutar()
        except Exception as error:  # la demo nunca se detiene por un escenario
            verificaciones = [(f"error inesperado: {error}", False)]
        for descripcion, ok in verificaciones:
            print(f"  [{'OK' if ok else 'FALLA'}] {descripcion}")
        exito = all(ok for _, ok in verificaciones)
        print(f"  -> {'APROBADO' if exito else 'NO APROBADO'} ({time.perf_counter() - inicio:.1f} s)")
        self.resultados.append((f"{numero}. {titulo}", exito))

    def mostrar(self, tiquete: dict) -> None:
        """Resumen del tiquete y, si se pidio, la guia generada."""
        d = tiquete["diagnostico"]
        causas = ", ".join(c["id"] for c in d["causas"][:3]) or "sin causa aplicable"
        print(f"  Tiquete {tiquete['id']}: {d['tipo_registro']}, {d['prioridad'].upper()} "
              f"(impacto {d['impacto']} x urgencia {d['urgencia']}), SLA {d['sla_horas_resolucion']:g} h, "
              f"nivel {d['nivel']}, estado {tiquete['estado']}")
        print(f"  Causas: {causas}")
        if d["causas_descartadas"]:
            print("  Descartadas: " + "; ".join(f"{c['id']} ({c['motivo']})"
                                                for c in d["causas_descartadas"]))
        print(f"  Motivo: {d['motivo']}  |  Reglas: {', '.join(d['reglas_aplicadas'])}")
        print(f"  Guia generada por: {d['resultado_ia']}")
        if self.mostrar_textos:
            print("  --- Guia para el usuario ---")
            print("  " + d["guia_usuario"].replace("\n", "\n  "))


# --- Escenarios ------------------------------------------------------------

def escenario_1(demo: Demo):
    t = demo.crear(**RED)["tiquete"]
    demo.mostrar(t)
    d = t["diagnostico"]
    ids = [c["id"] for c in d["causas"]]
    return [
        ("causas probables en orden: cable desconectado y DHCP", ids[:2] == ["cable_desconectado",
                                                                             "dhcp_sin_respuesta"]),
        ("prioridad P3", d["prioridad"] == "p3"),
        ("se atiende en nivel 1", d["nivel"] == 1 and t["estado"] == "registrado"),
        ("pasos en orden", [p["orden"] for p in d["pasos"]] == [1, 2, 3]),
        ("la guia incluye el primer paso", "cable" in d["guia_usuario"].lower()),
    ]


def escenario_2(demo: Demo):
    t = demo.crear(usuario_id=1, servicio="correo", sintomas=["no_recibe_correos", "no_envia_correos"],
                   alcance="departamento", urgencia="alta")["tiquete"]
    demo.mostrar(t)
    d = t["diagnostico"]
    return [
        ("impacto departamento y urgencia alta", (d["impacto"], d["urgencia"]) == ("departamento", "alta")),
        ("prioridad P1 segun la matriz del motor", d["prioridad"] == "p1"),
        ("escala a nivel 2, infraestructura y correo",
         d["nivel"] == 2 and t["grupo_resolutor_id"] == 6 and t["estado"] == "escalado"),
    ]


def escenario_3(demo: Demo):
    t = demo.crear(usuario_id=5, servicio="cuentas", sintomas=["cuenta_bloqueada"],
                   alcance="individual", urgencia="media")["tiquete"]
    demo.mostrar(t)
    pasos = [p["codigo"] for p in t["diagnostico"]["pasos"]]
    print("  Variante: el usuario ya aplico los 4 pasos (requiere al grupo de cuentas)")
    agotado = demo.crear(usuario_id=6, servicio="cuentas", sintomas=["cuenta_bloqueada"],
                         alcance="individual", urgencia="media",
                         pasos_ya_aplicados=pasos)["tiquete"]
    return [
        ("4 pasos de desbloqueo en orden",
         pasos == [f"intentos_fallidos_{n}" for n in range(1, 5)]),
        ("se atiende en nivel 1", t["diagnostico"]["nivel"] == 1),
        ("con los pasos agotados escala al grupo de cuentas y accesos",
         agotado["grupo_resolutor_id"] == 3 and agotado["estado"] == "escalado"),
    ]


def escenario_4(demo: Demo):
    individual = demo.crear(usuario_id=9, servicio="impresoras", sintomas=["no_imprime"],
                            alcance="individual", urgencia="baja")["tiquete"]
    demo.mostrar(individual)
    print("  Variante: la impresora de red no imprime para todo el departamento")
    departamento = demo.crear(usuario_id=10, servicio="impresoras", sintomas=["no_imprime"],
                              alcance="departamento", urgencia="baja")["tiquete"]
    return [
        ("causa probable: cola de impresion detenida",
         individual["diagnostico"]["causa_principal"] == "cola_impresion_detenida"),
        ("alcance individual: nivel 1", individual["diagnostico"]["nivel"] == 1),
        ("alcance departamento: nivel 2, soporte de equipos",
         departamento["diagnostico"]["nivel"] == 2 and departamento["grupo_resolutor_id"] == 4),
    ]


def escenario_5(demo: Demo):
    previos = [demo.crear(**{**RED, "usuario_id": u, "activo_id": None,
                             "sintomas": ["sin_internet"]})["tiquete"]["id"] for u in (4, 3, 4)]
    print(f"  Ya hay 3 tiquetes abiertos de red en Ventas: {previos}")
    t = demo.crear(**{**RED, "alcance": "departamento"})["tiquete"]
    demo.mostrar(t)
    d = t["diagnostico"]
    descartadas = {c["id"] for c in d["causas_descartadas"]}
    return [
        ("posible_problema_masivo = true", d["posible_problema_masivo"] is True),
        ("tipo de registro: problema", d["tipo_registro"] == "problema"),
        ("escala a redes en nivel 2 o 3", t["grupo_resolutor_id"] == 2 and d["nivel"] in (2, 3)),
        ("causa individual descartada (cable)", "cable_desconectado" in descartadas),
        ("relaciona los incidentes abiertos", set(previos) <= set(d["incidentes_relacionados"])),
    ]


def escenario_6(demo: Demo):
    descripcion = ("Hola, soy Laura Mendez Solis, cedula 1-1111-0001. Mi contraseña es "
                   "Verano2026 y no puedo entrar a la VPN.")
    print(f"  Texto del usuario: {descripcion}")
    t = demo.crear(usuario_id=1, servicio="vpn", sintomas=["vpn_caida"], alcance="individual",
                   urgencia="media", descripcion=descripcion)["tiquete"]
    prompt = demo.api.get(f"/tiquetes/{t['id']}/ia").json()["prompt_ia"]
    mensaje_usuario = json.loads(prompt)[1]["content"]
    print("  Mensaje enviado a la IA (inicio):")
    print("  " + "\n  ".join(mensaje_usuario.splitlines()[:8]) + "\n  ...")
    return [(f"el prompt no contiene '{dato}'", dato not in prompt)
            for dato in ("Verano2026", "1-1111-0001", "Laura", "Mendez")]


def escenario_7(config: Configuracion):
    def ejecutar(demo: Demo):
        apagado = ClienteOllama(config.model_copy(update={"ollama_url": "http://127.0.0.1:9",
                                                          "ollama_timeout_s": 2}))
        app.dependency_overrides[obtener_cliente_ia] = lambda: apagado
        try:
            respuesta = demo.api.post("/tiquetes", json={**RED, "usuario_id": 2, "activo_id": None})
        finally:
            app.dependency_overrides.pop(obtener_cliente_ia, None)
        d = respuesta.json()["tiquete"]["diagnostico"] if respuesta.status_code == 201 else {}
        print(f"  Ollama apuntando a un puerto cerrado -> HTTP {respuesta.status_code}, "
              f"resultado {d.get('resultado_ia')}")
        return [
            ("responde 201, sin error", respuesta.status_code == 201),
            ("estado fallback (plantilla)", d.get("resultado_ia") == "fallback"),
            ("la guia trae los pasos del motor", "Revisar que el cable" in d.get("guia_usuario", "")),
        ]
    return ejecutar


# --- Preparacion -------------------------------------------------------------

def preparar_api(sin_ia: bool) -> TestClient:
    motor = crear_motor("sqlite://")
    Base.metadata.create_all(motor)
    sesion = Session(motor, expire_on_commit=False)
    cargar_datos(sesion)
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    if sin_ia:
        app.dependency_overrides[obtener_cliente_ia] = lambda: None
    return TestClient(app)  # sin "with": no ejecuta el arranque de la API real


def main() -> None:
    parser = argparse.ArgumentParser(description="Recorrido de los 7 escenarios de validacion.")
    parser.add_argument("--sin-ia", action="store_true", help="no llama a Ollama (usa plantillas)")
    parser.add_argument("--sin-textos", action="store_true", help="no imprime las guias completas")
    args = parser.parse_args()
    # La demo muestra sus propios resultados; los registros internos solo si hay errores.
    logging.getLogger().setLevel(logging.ERROR)

    config = obtener_configuracion()
    cliente = preparar_api(args.sin_ia)
    salud = cliente.get("/salud").json()
    print(f"Estado: API {salud['api']}, Prolog {salud['prolog']}, IA {salud['ia']}"
          f"{' (desactivada con --sin-ia)' if args.sin_ia else ''}")
    if salud["prolog"] != "ok":
        sys.exit("Prolog no esta disponible: la demo necesita el motor de inferencia.")

    demo = Demo(cliente, mostrar_textos=not args.sin_textos)
    escenarios = [
        ("Usuario sin internet + VPN caida, alcance individual", lambda: escenario_1(demo)),
        ("Caida de correo en todo un departamento", lambda: escenario_2(demo)),
        ("Cuenta bloqueada por intentos fallidos", lambda: escenario_3(demo)),
        ("Impresora de red fuera de servicio", lambda: escenario_4(demo)),
        ("Sin internet + VPN + 3 companeros con lo mismo", lambda: escenario_5(demo)),
        ("Texto con contrasena y cedula", lambda: escenario_6(demo)),
        ("Ollama apagado", lambda: escenario_7(config)(demo)),
    ]
    for numero, (titulo, ejecutar) in enumerate(escenarios, start=1):
        demo.escenario(numero, titulo, ejecutar)

    aprobados = sum(ok for _, ok in demo.resultados)
    print(f"\n{'=' * 78}\nRESUMEN: {aprobados} de {len(demo.resultados)} escenarios aprobados\n{'=' * 78}")
    for titulo, ok in demo.resultados:
        print(f"  [{'OK' if ok else 'FALLA'}] {titulo}")
    app.dependency_overrides.clear()
    sys.exit(0 if aprobados == len(demo.resultados) else 1)


if __name__ == "__main__":
    main()
