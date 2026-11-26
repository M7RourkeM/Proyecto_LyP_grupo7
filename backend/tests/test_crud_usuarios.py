"""Pruebas del CRUD de usuarios."""

from app.models import Tiquete

NUEVO = {"nombre": "Ana Rojas Mora", "correo": "ana.rojas@empresa-demo.test",
         "telefono": "8800-5555", "identificacion": "2-0222-0333", "departamento_id": 1}


# --- Caso feliz ---------------------------------------------------------

def test_ciclo_completo_crear_consultar_modificar_eliminar(api):
    creado = api.post("/usuarios", json=NUEVO)
    assert creado.status_code == 201
    usuario_id = creado.json()["id"]

    assert api.get(f"/usuarios/{usuario_id}").json()["correo"] == NUEVO["correo"]

    modificado = api.patch(f"/usuarios/{usuario_id}", json={"telefono": "8800-6666"})
    assert modificado.status_code == 200
    assert modificado.json()["telefono"] == "8800-6666"
    assert modificado.json()["nombre"] == NUEVO["nombre"]  # PATCH no toca lo demas

    assert api.delete(f"/usuarios/{usuario_id}").status_code == 204
    assert api.get(f"/usuarios/{usuario_id}").status_code == 404


def test_correo_se_normaliza_a_minusculas(api):
    datos = {**NUEVO, "correo": "  Ana.Rojas@Empresa-Demo.TEST "}
    assert api.post("/usuarios", json=datos).json()["correo"] == "ana.rojas@empresa-demo.test"


def test_desactivar_usuario(api):
    respuesta = api.patch("/usuarios/1", json={"activo": False})
    assert respuesta.json()["activo"] is False


# --- Listado y paginacion -------------------------------------------------

def test_listado_paginado(api):
    pagina = api.get("/usuarios", params={"pagina": 2, "tamano": 4}).json()
    assert pagina["total"] == 10
    assert pagina["pagina"] == 2 and pagina["tamano"] == 4
    assert [u["id"] for u in pagina["items"]] == [5, 6, 7, 8]


def test_ultima_pagina_incompleta_y_pagina_vacia(api):
    assert len(api.get("/usuarios", params={"pagina": 3, "tamano": 4}).json()["items"]) == 2
    assert api.get("/usuarios", params={"pagina": 9, "tamano": 4}).json()["items"] == []


def test_filtro_por_departamento(api):
    pagina = api.get("/usuarios", params={"departamento_id": 1}).json()
    assert pagina["total"] == 2
    assert all(u["departamento_id"] == 1 for u in pagina["items"])


def test_tamano_de_pagina_fuera_de_rango_es_422(api):
    assert api.get("/usuarios", params={"tamano": 500}).status_code == 422
    assert api.get("/usuarios", params={"pagina": 0}).status_code == 422


# --- Errores --------------------------------------------------------------

def test_usuario_inexistente_es_404(api):
    respuesta = api.get("/usuarios/999")
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "Usuario 999 no existe"


def test_correo_duplicado_es_409(api):
    datos = {**NUEVO, "correo": "lmendez@empresa-demo.test"}
    respuesta = api.post("/usuarios", json=datos)
    assert respuesta.status_code == 409
    assert "correo" in respuesta.json()["detail"]


def test_modificar_con_correo_de_otro_es_409(api):
    assert api.patch("/usuarios/2", json={"correo": "lmendez@empresa-demo.test"}).status_code == 409


def test_modificar_con_su_propio_correo_no_es_conflicto(api):
    assert api.patch("/usuarios/1", json={"correo": "lmendez@empresa-demo.test"}).status_code == 200


def test_formatos_invalidos_son_422(api):
    for campo, valor in [("correo", "sin-arroba"), ("identificacion", "123456789"),
                         ("telefono", "abc"), ("nombre", "A")]:
        respuesta = api.post("/usuarios", json={**NUEVO, campo: valor})
        assert respuesta.status_code == 422, campo


def test_departamento_inexistente_es_422(api):
    respuesta = api.post("/usuarios", json={**NUEVO, "departamento_id": 99})
    assert respuesta.status_code == 422
    assert "departamento_id" in respuesta.json()["detail"]


def test_null_en_campo_obligatorio_es_422(api):
    respuesta = api.patch("/usuarios/1", json={"nombre": None})
    assert respuesta.status_code == 422
    assert "nombre" in respuesta.json()["detail"]


def test_eliminar_usuario_con_activos_es_409(api):
    respuesta = api.delete("/usuarios/1")  # tiene la laptop LAP-001
    assert respuesta.status_code == 409
    assert "activos asignados" in respuesta.json()["detail"]


def test_eliminar_usuario_con_tiquetes_es_409(api, sesion_con_datos):
    nuevo_id = api.post("/usuarios", json=NUEVO).json()["id"]
    sesion_con_datos.add(Tiquete(usuario_id=nuevo_id, departamento_id=1, servicio="red",
                                 alcance="individual", urgencia_reportada="media"))
    sesion_con_datos.commit()
    respuesta = api.delete(f"/usuarios/{nuevo_id}")
    assert respuesta.status_code == 409
    assert "tiquetes" in respuesta.json()["detail"]
