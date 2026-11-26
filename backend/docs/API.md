# Documentación de la API

## Descripción general

La API del backend expone, mediante HTTP y JSON, las funciones de la mesa de servicios: la administración de usuarios, agentes y activos; el registro de tiquetes con diagnóstico automático; el ciclo de vida de cada caso; la retroalimentación sobre las soluciones aplicadas; y los indicadores del panel. Está construida con FastAPI, por lo que la documentación interactiva se genera a partir del propio código y se consulta en `http://localhost:8000/docs` cuando el servidor está en ejecución. En esa página cada endpoint incluye un ejemplo de cuerpo y la lista de sus respuestas posibles.

## Convenciones

- Todas las peticiones y respuestas usan JSON con codificación UTF-8, salvo `GET /retroalimentacion/hechos.pl`, que devuelve texto plano.
- Las fechas se expresan en formato ISO 8601 y siempre en UTC, con el sufijo `Z` (por ejemplo, `2026-11-26T14:30:00Z`). Los parámetros de fecha que recibe la API deben incluir la zona horaria.
- Los listados se paginan con los parámetros `pagina` (desde 1) y `tamano` (de 1 a 100, 20 por defecto). La respuesta tiene la forma `{"items": [...], "total": n, "pagina": p, "tamano": t}`.
- Las modificaciones usan `PATCH`, que cambia únicamente los campos enviados.
- Los códigos de diagnóstico (síntomas, causas, grupos, departamentos) son los átomos de la base de conocimiento en Prolog, por ejemplo `sin_internet` o `mesa_ayuda`. La lista vigente de síntomas y datos de contexto se obtiene con `GET /prolog/catalogo`.

## Códigos de respuesta

| Código | Significado en esta API |
|---|---|
| 200 | Consulta o modificación correcta. |
| 201 | Registro creado. |
| 204 | Registro eliminado; la respuesta no tiene cuerpo. |
| 404 | El recurso indicado en la ruta no existe. |
| 409 | Conflicto: dato duplicado, registro con dependencias, transición de estado no permitida u operación que no corresponde al estado actual. |
| 422 | Datos inválidos: formato incorrecto, referencia a un registro inexistente, campo obligatorio nulo o síntoma que el motor no reconoce. |
| 502 | El motor de inferencia produjo un error interno. |
| 503 | El motor de inferencia no está disponible (SWI-Prolog no instalado o base de conocimiento inexistente). |
| 504 | El motor de inferencia excedió el tiempo límite. |

Los errores tienen la forma `{"detail": "mensaje"}`. Los errores del motor agregan el campo `codigo` y, si el problema es un síntoma desconocido, el campo `desconocidos` con la lista de valores no reconocidos. Ninguna falla del motor ni de la IA produce un error 500.

## Endpoints

### Sistema y catálogos

| Método | Ruta | Cuerpo | Respuesta | Códigos |
|---|---|---|---|---|
| GET | `/salud` | — | Estado de la API, de Prolog y de la IA (`ok` o `caido`) | 200 |
| GET | `/departamentos` | — | Lista de departamentos | 200 |
| GET | `/grupos` | — | Lista de grupos resolutores con su nivel | 200 |
| GET | `/prolog/catalogo` | — | Síntomas, peticiones, contextos y evidencias que reconoce el motor | 200, 502, 503, 504 |
| POST | `/prolog/diagnostico` | Entrada del contrato 3.1 | Diagnóstico del contrato 3.2, sin crear un tiquete | 200, 422, 502, 503, 504 |

`GET /salud` responde siempre 200; una dependencia caída se informa como `caido` en lugar de producir un error. Los departamentos y grupos son de solo lectura porque sus códigos deben coincidir con los átomos del motor.

### Usuarios

| Método | Ruta | Cuerpo | Respuesta | Códigos |
|---|---|---|---|---|
| GET | `/usuarios` | — | Página de usuarios; filtros `departamento_id`, `activo` | 200, 422 |
| GET | `/usuarios/{id}` | — | Usuario | 200, 404 |
| POST | `/usuarios` | `nombre`, `correo`, `telefono`, `identificacion`, `departamento_id` | Usuario creado | 201, 409, 422 |
| PATCH | `/usuarios/{id}` | Cualquier campo, más `activo` | Usuario modificado | 200, 404, 409, 422 |
| DELETE | `/usuarios/{id}` | — | Sin cuerpo | 204, 404, 409 |
| GET | `/usuarios/{id}/historial` | — | Tiquetes del usuario y categorías recurrentes | 200, 404 |

La identificación debe tener el formato de cédula física `X-XXXX-XXXX`. Un usuario con tiquetes o con activos asignados no se elimina (409): para conservar la trazabilidad se desactiva con `PATCH {"activo": false}`.

### Agentes

| Método | Ruta | Cuerpo | Respuesta | Códigos |
|---|---|---|---|---|
| GET | `/agentes` | — | Página de agentes; filtros `grupo_resolutor_id`, `activo` | 200, 422 |
| GET | `/agentes/{id}` | — | Agente | 200, 404 |
| POST | `/agentes` | `nombre`, `correo`, `grupo_resolutor_id` | Agente creado | 201, 409, 422 |
| PATCH | `/agentes/{id}` | Cualquier campo, más `activo` | Agente modificado | 200, 404, 409, 422 |
| DELETE | `/agentes/{id}` | — | Sin cuerpo | 204, 404, 409 |

Un agente con tiquetes asignados o con registros en el historial no se elimina (409).

### Activos

| Método | Ruta | Cuerpo | Respuesta | Códigos |
|---|---|---|---|---|
| GET | `/activos` | — | Página de activos; filtros `departamento_id`, `usuario_id`, `tipo` | 200, 422 |
| GET | `/activos/{id}` | — | Activo | 200, 404 |
| POST | `/activos` | `codigo_inventario`, `tipo`, `marca_modelo`, `sistema_operativo`, `ubicacion`, `departamento_id`, `usuario_id` | Activo creado | 201, 409, 422 |
| PATCH | `/activos/{id}` | Cualquier campo | Activo modificado o reasignado | 200, 404, 409, 422 |
| DELETE | `/activos/{id}` | — | Sin cuerpo | 204, 404, 409 |
| GET | `/activos/{id}/historial` | — | Tiquetes del activo y categorías recurrentes | 200, 404 |

El código de inventario tiene el formato `AAA-000` y se guarda en mayúsculas. Los tipos permitidos son `laptop`, `escritorio`, `impresora`, `telefono`, `servidor` y `otro`. Un activo compartido, como una impresora de red, se registra con `usuario_id` nulo. No se asignan activos a usuarios desactivados (409).

### Tiquetes

| Método | Ruta | Cuerpo | Respuesta | Códigos |
|---|---|---|---|---|
| POST | `/tiquetes` | Ver ejemplo | Tiquete con diagnóstico, recurrencia y aviso | 201, 422, 502, 503, 504 |
| GET | `/tiquetes` | — | Página de tiquetes; filtros `estado`, `prioridad`, `departamento_id`, `grupo_resolutor_id`, `usuario_id`, `activo_id` | 200, 422 |
| GET | `/tiquetes/{id}` | — | Tiquete con diagnóstico, pasos e historial | 200, 404 |
| POST | `/tiquetes/{id}/transiciones` | `estado`, `agente_id`, `comentario`, `grupo_resolutor_id` | Tiquete actualizado | 200, 404, 409, 422 |
| GET | `/tiquetes/{id}/historial` | — | Cambios de estado con fecha, agente y comentario | 200, 404 |
| POST | `/tiquetes/{id}/diagnostico` | — | Reintenta el diagnóstico de un tiquete registrado sin él | 200, 404, 409, 422, 502, 503, 504 |
| GET | `/tiquetes/{id}/ia` | — | Auditoría de la IA: prompt enviado, guía, nota y resultado | 200, 404 |

Ejemplo de registro:

```json
{
  "usuario_id": 3,
  "activo_id": 3,
  "servicio": "red",
  "componente": "red_cableada",
  "sintomas": ["sin_internet", "vpn_caida"],
  "alcance": "individual",
  "urgencia": "media",
  "descripcion": "Desde esta mañana no tengo Internet ni VPN.",
  "pasos_ya_aplicados": [],
  "sospecha_seguridad": false
}
```

Al registrar un tiquete, el backend busca tiquetes abiertos similares del mismo departamento, consulta al motor Prolog, guarda el diagnóstico con sus pasos y solicita a la IA la guía para el usuario y la nota técnica. Si el motor indica escalamiento, el tiquete pasa al estado `escalado` en la misma operación. Si el síntoma no existe en la base de conocimiento, se responde 422 y no se crea el tiquete. Si el motor no está disponible, el tiquete se registra sin diagnóstico, asignado a la mesa de ayuda, y la respuesta incluye un aviso; el diagnóstico puede reintentarse después con `POST /tiquetes/{id}/diagnostico`.

Transiciones de estado permitidas:

| Estado actual | Estados siguientes |
|---|---|
| `registrado` | `en_atencion`, `escalado` |
| `en_atencion` | `escalado`, `resuelto` |
| `escalado` | `en_atencion`, `resuelto` |
| `resuelto` | `cerrado`, `en_atencion` (reapertura) |
| `cerrado` | ninguno (estado final) |

Una transición no permitida responde 409. Pasar a `en_atencion` exige `agente_id`. Escalar un caso de primer nivel exige `grupo_resolutor_id` de un grupo de nivel 2 o 3. Cada cambio queda en el historial.

### Retroalimentación

| Método | Ruta | Cuerpo | Respuesta | Códigos |
|---|---|---|---|---|
| POST | `/tiquetes/{id}/retroalimentacion` | `funciono`, `paso_que_resolvio`, `comentario` | Retroalimentación registrada | 201, 404, 409, 422 |
| GET | `/tiquetes/{id}/retroalimentacion` | — | Retroalimentación del tiquete | 200, 404 |
| GET | `/retroalimentacion/estadisticas` | — | Efectividad por causa y por paso | 200 |
| GET | `/retroalimentacion/hechos.pl` | — | Hechos `resultado_solucion/2` en texto Prolog | 200 |

La retroalimentación se registra una sola vez por tiquete y solo cuando está resuelto o cerrado. `paso_que_resolvio` debe ser el código de un paso del diagnóstico del tiquete, por ejemplo `cable_desconectado_2`. Los resultados se envían al motor en cada diagnóstico posterior y modifican el orden de las causas probables.

### Indicadores

| Método | Ruta | Parámetros | Respuesta | Códigos |
|---|---|---|---|---|
| GET | `/indicadores` | `desde`, `hasta` (opcionales, con zona horaria) | Indicadores del panel | 200, 422 |

La respuesta incluye el total de tiquetes, los abiertos, los resueltos, los resueltos en primer nivel (sin escalamiento), los escalados, el cumplimiento de SLA y la distribución por estado, prioridad, grupo resolutor y tipo de registro. El cumplimiento de SLA se mide en horas hábiles, de lunes a viernes entre las 8:00 y las 16:00, hora de Costa Rica, porque así define el SLA la base de conocimiento. No se descuentan feriados.

## Contrato con el motor de inferencia

El contrato acordado entre los integrantes (secciones 3.1 y 3.2) se mantiene en su estructura. La integración con la base de conocimiento real introdujo las siguientes diferencias, que el frontend debe considerar:

| Campo | Acuerdo inicial | Implementación | Motivo |
|---|---|---|---|
| `prioridad` | `"P3"` | `"p3"` | Es el átomo que usa la base de conocimiento. |
| `grupo_resolutor` | `"mesa_servicios_n1"` | `"mesa_ayuda"` | Nombre definido en la base de conocimiento. |
| `causas_descartadas` | Lista de códigos | Lista de `{"id", "motivo"}` | El motor explica por qué descarta cada causa. |
| `sla_horas` | Horas de resolución | Horas hábiles de resolución | El motor define el SLA en días hábiles. |
| Campos nuevos | — | `motivo`, `sla_horas_respuesta` | Justificación de la decisión y tiempo de primera respuesta. |
| `pasos_ya_aplicados` | Lista de códigos | Se envía la lista; el motor usa la cantidad | Regla de pasos agotados. |
| `requiere_permisos_admin` | Dato del tiquete | Lo decide el motor por causa | Hecho `requiere_permisos_admin/1` de la base. |
