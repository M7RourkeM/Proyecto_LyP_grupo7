"""Pruebas del endpoint /salud y de la verificacion de dependencias."""

import asyncio
import shutil
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Configuracion, obtener_configuracion
from app.main import app
from app.services import salud

hay_swipl = shutil.which("swipl") is not None


def config_prueba(**cambios) -> Configuracion:
    # Puerto 9 (discard): nadie escucha, asi la IA queda "caida" sin esperar.
    valores = {"ollama_url": "http://127.0.0.1:9", "salud_timeout_s": 2.0}
    valores.update(cambios)
    return Configuracion(**valores)


def transporte_ollama(modelos: list[str]) -> httpx.MockTransport:
    def responder(peticion: httpx.Request) -> httpx.Response:
        assert peticion.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": m} for m in modelos]})
    return httpx.MockTransport(responder)


@pytest.fixture
def cliente():
    # Funcion sin argumentos: FastAPI trataria **cambios como parametro de consulta.
    app.dependency_overrides[obtener_configuracion] = lambda: config_prueba()
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Endpoint -------------------------------------------------------

def test_salud_responde_200_con_las_tres_claves(cliente):
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert set(respuesta.json()) == {"api", "prolog", "ia"}
    assert respuesta.json()["api"] == "ok"


def test_salud_con_ollama_caido_no_falla(cliente):
    assert cliente.get("/salud").json()["ia"] == "caido"


def test_salud_aparece_en_swagger(cliente):
    assert "/salud" in cliente.get("/openapi.json").json()["paths"]


# --- Prolog ---------------------------------------------------------

@pytest.mark.skipif(not hay_swipl, reason="SWI-Prolog no instalado")
def test_prolog_ok_con_la_base_real():
    assert salud.verificar_prolog(config_prueba()) == "ok"


@pytest.mark.skipif(not hay_swipl, reason="SWI-Prolog no instalado")
def test_prolog_ok_con_ruta_que_tiene_espacios_y_ampersand(tmp_path):
    carpeta = tmp_path / "Cuatri 3 2026" / "Proyecto_L&P"
    carpeta.mkdir(parents=True)
    kb = carpeta / "kb.pl"
    kb.write_text("hecho(uno).\n", encoding="utf-8")
    assert salud.verificar_prolog(config_prueba(prolog_kb=kb)) == "ok"


@pytest.mark.skipif(not hay_swipl, reason="SWI-Prolog no instalado")
def test_prolog_caido_si_la_base_tiene_error_de_sintaxis(tmp_path):
    kb = tmp_path / "rota.pl"
    kb.write_text("hecho(uno.\n", encoding="utf-8")
    assert salud.verificar_prolog(config_prueba(prolog_kb=kb)) == "caido"


def test_prolog_caido_si_no_existe_la_base(tmp_path):
    config = config_prueba(prolog_kb=tmp_path / "no_existe.pl")
    assert salud.verificar_prolog(config) == "caido"


def test_prolog_caido_si_no_esta_instalado():
    config = config_prueba(swipl_ejecutable="swipl_inexistente_123")
    assert salud.verificar_prolog(config) == "caido"


def test_prolog_caido_por_timeout(monkeypatch):
    def demasiado_lento(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="swipl", timeout=1)
    monkeypatch.setattr(salud.subprocess, "run", demasiado_lento)
    assert salud.verificar_prolog(config_prueba()) == "caido"


# --- IA ---------------------------------------------------------------

def test_ia_ok_si_ollama_tiene_el_modelo():
    config = config_prueba(ollama_url="http://ollama.local", ollama_modelo="qwen2.5:3b")
    resultado = asyncio.run(salud.verificar_ia(config, transporte_ollama(["qwen2.5:3b"])))
    assert resultado == "ok"


def test_ia_caida_si_falta_el_modelo():
    config = config_prueba(ollama_url="http://ollama.local", ollama_modelo="qwen2.5:3b")
    resultado = asyncio.run(salud.verificar_ia(config, transporte_ollama(["llama3.1:8b"])))
    assert resultado == "caido"


def test_ia_caida_si_ollama_no_responde():
    assert asyncio.run(salud.verificar_ia(config_prueba())) == "caido"


def test_ia_caida_si_ollama_devuelve_error():
    transporte = httpx.MockTransport(lambda peticion: httpx.Response(500))
    config = config_prueba(ollama_url="http://ollama.local")
    assert asyncio.run(salud.verificar_ia(config, transporte)) == "caido"
