"""Pruebas del CRUD de agentes y activos, y de los catalogos."""

from app.models import HistorialTiquete, Tiquete

AGENTE = {"nombre": "Pablo Mora Leon", "correo": "pmora.soporte@empresa-demo.test",
          "grupo_resolutor_id": 2}
ACTIVO = {"codigo_inventario": "lap-010", "tipo": "laptop", "marca_modelo": "Dell Latitude 5440",
          "sistema_operativo": "Windows 11", "ubicacion": "Edificio A, piso 2",
          "departamento_id": 1, "usuario_id": 1}


def crear_tiquete(sesion, **campos) -> Tiquete:
    tiquete = Tiquete(usuario_id=1, departamento_id=1, servicio="red", alcance="individual",
                      urgencia_reportada="media", **campos)
    sesion.add(tiquete)
    sesion.commit()
    return tiquete


# --- Agentes ---------------------------------------------------------------

def test_agente_ciclo_completo(api):
    agente_id = api.post("/agentes", json=AGENTE).json()["id"]
    assert api.patch(f"/agentes/{agente_id}", json={"grupo_resolutor_id": 1}).status_code == 200
    assert api.get(f"/agentes/{agente_id}").json()["grupo_resolutor_id"] == 1
    assert api.delete(f"/agentes/{agente_id}").status_code == 204


def test_agentes_filtrados_por_grupo(api):
    pagina = api.get("/agentes", params={"grupo_resolutor_id": 1}).json()
    assert pagina["total"] == 2  # dos agentes de mesa de ayuda en la semilla


def test_agente_con_grupo_inexistente_es_422(api):
    assert api.post("/agentes", json={**AGENTE, "grupo_resolutor_id": 99}).status_code == 422


def test_agente_correo_duplicado_es_409(api):
    datos = {**AGENTE, "correo": "dsoto.soporte@empresa-demo.test"}
    assert api.post("/agentes", json=datos).status_code == 409


def test_eliminar_agente_con_historial_es_409(api, sesion_con_datos):
    tiquete = crear_tiquete(sesion_con_datos)
    sesion_con_datos.add(HistorialTiquete(tiquete_id=tiquete.id, estado_nuevo="en_atencion",
                                          agente_id=1))
    sesion_con_datos.commit()
    respuesta = api.delete("/agentes/1")
    assert respuesta.status_code == 409
    assert "historial" in respuesta.json()["detail"]


def test_agente_inexistente_es_404(api):
    assert api.patch("/agentes/999", json={"nombre": "Nadie"}).status_code == 404


# --- Activos ---------------------------------------------------------------

def test_activo_ciclo_completo_y_codigo_en_mayusculas(api):
    creado = api.post("/activos", json=ACTIVO)
    assert creado.status_code == 201
    assert creado.json()["codigo_inventario"] == "LAP-010"
    activo_id = creado.json()["id"]
    assert api.patch(f"/activos/{activo_id}", json={"usuario_id": None}).json()["usuario_id"] is None
    assert api.delete(f"/activos/{activo_id}").status_code == 204


def test_activos_filtrados_por_tipo_y_departamento(api):
    pagina = api.get("/activos", params={"tipo": "impresora"}).json()
    assert pagina["total"] == 2
    pagina = api.get("/activos", params={"departamento_id": 4}).json()  # tecnologia
    assert pagina["total"] == 4


def test_activo_tipo_invalido_es_422(api):
    assert api.post("/activos", json={**ACTIVO, "tipo": "tostadora"}).status_code == 422
    assert api.get("/activos", params={"tipo": "tostadora"}).status_code == 422


def test_activo_codigo_duplicado_es_409(api):
    assert api.post("/activos", json={**ACTIVO, "codigo_inventario": "LAP-001"}).status_code == 409


def test_activo_con_usuario_inexistente_es_422(api):
    respuesta = api.post("/activos", json={**ACTIVO, "usuario_id": 999})
    assert respuesta.status_code == 422
    assert "usuario_id" in respuesta.json()["detail"]


def test_no_se_asigna_activo_a_usuario_desactivado(api):
    api.patch("/usuarios/2", json={"activo": False})
    assert api.post("/activos", json={**ACTIVO, "usuario_id": 2}).status_code == 409


def test_eliminar_activo_con_tiquetes_es_409(api, sesion_con_datos):
    crear_tiquete(sesion_con_datos, activo_id=1)
    assert api.delete("/activos/1").status_code == 409


# --- Catalogos y documentacion -------------------------------------------

def test_catalogos(api):
    assert len(api.get("/departamentos").json()) == 5
    grupos = api.get("/grupos").json()
    assert len(grupos) == 7
    assert grupos[0]["nivel"] == 1 and grupos[-1]["nivel"] == 3


def test_swagger_documenta_endpoints_y_ejemplos(api):
    esquema = api.get("/openapi.json").json()
    for ruta in ["/usuarios", "/usuarios/{usuario_id}", "/agentes", "/activos", "/grupos"]:
        assert ruta in esquema["paths"], ruta
    ejemplos = esquema["components"]["schemas"]["UsuarioCrear"]["examples"]
    assert ejemplos[0]["correo"].endswith(".test")
    assert "404" in esquema["paths"]["/usuarios/{usuario_id}"]["get"]["responses"]
