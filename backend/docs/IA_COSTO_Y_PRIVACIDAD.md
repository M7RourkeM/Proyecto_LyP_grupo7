# Inteligencia artificial: costo y privacidad

## Modelo utilizado

La generación de textos se realiza con un modelo de lenguaje que se ejecuta localmente mediante Ollama, sin servicios externos.

| Característica | Valor |
|---|---|
| Servidor de modelos | Ollama 0.40.18, ejecutado en el mismo equipo que el backend |
| Modelo | `qwen2.5:3b` (Qwen2.5, 3,09 mil millones de parámetros, cuantización Q4_K_M) |
| Tamaño de la descarga | 1,9 GB |
| Memoria ocupada al ejecutarse | 2,2 GB, cargado por completo en la GPU (medido con `ollama ps`) |
| Licencia del modelo | Qwen Research License: uso libre con fines de investigación y académicos; el uso comercial requiere un acuerdo con el autor |
| Interfaz | `POST http://localhost:11434/api/chat`, con un esquema JSON en el campo `format` |

Se eligió el tamaño de 3 mil millones de parámetros porque cabe por completo en la memoria de una GPU de computadora portátil y responde en pocos segundos. En el equipo de prueba (16 GB de RAM y GPU dedicada), con el modelo ya cargado, una respuesta válida en el primer intento tomó entre 4,3 y 4,9 segundos, y una respuesta que necesitó el reintento tomó 10,7 segundos. La primera consulta después de iniciar Ollama incluye la carga del modelo en memoria y puede superar el minuto; por eso el backend precarga el modelo al arrancar y solicita a Ollama que lo mantenga cargado durante 30 minutos.

El modelo se puede cambiar sin modificar código, mediante la variable `OLLAMA_MODELO`. La alternativa evaluada es `qwen2.5:7b` (unos 4,7 GB), que sigue mejor las instrucciones de formato y se distribuye con licencia Apache 2.0, a cambio de requerir más memoria de video.

### Instalación

En Windows, desde PowerShell:

```
winget install --id Ollama.Ollama -e
ollama pull qwen2.5:3b
ollama list
```

Después de instalarse, Ollama queda en ejecución en segundo plano. Para precargar el modelo antes de una demostración:

```
ollama run qwen2.5:3b ""
```

## Costo

El componente de IA no tiene costo de operación:

- El modelo se descarga una vez y se ejecuta en el equipo local. No hay facturación por consulta, por cantidad de texto ni por tiempo de uso.
- No se utiliza ninguna API de pago y el sistema no requiere claves de API.
- Ollama es software libre (licencia MIT) y el modelo es de pesos abiertos.
- Los datos de los tiquetes no salen del equipo: la única comunicación de la IA es con `localhost`.

El único costo es el uso del hardware local (memoria, GPU y electricidad), el mismo que el de cualquier otra aplicación de escritorio.

## Privacidad: qué datos recibe la IA

La protección de datos se basa en dos barreras independientes. La primera es estructural: la IA nunca recibe el texto libre que escribe el usuario ni sus datos personales. La segunda es un sanitizador que se aplica a todo lo que forma parte del prompt, como defensa en profundidad por si algún dato sensible llegara por otro camino.

### Primera barrera: contenido del prompt

El prompt se construye exclusivamente con el diagnóstico estructurado del motor Prolog:

| Se envía a la IA | No se envía a la IA |
|---|---|
| Descripciones de los síntomas, tomadas del catálogo del motor | Descripción libre escrita por el usuario |
| Causas probables y causas descartadas, con su motivo | Nombre, correo, teléfono e identificación del usuario |
| Pasos de solución con su identificador y orden | Nombres de los agentes |
| Prioridad, impacto, urgencia y SLA | Datos del activo (código de inventario, ubicación) |
| Escalamiento, grupo resolutor y motivo | Identificadores de otros tiquetes |
| Código del departamento y del servicio | Historial y comentarios del caso |

### Segunda barrera: sanitizador

El módulo `app/ia/sanitizador.py` recorre todos los textos del contexto antes de construir el prompt y reemplaza los datos sensibles por marcadores:

| Dato | Ejemplos detectados | Marcador |
|---|---|---|
| Contraseñas y claves | "mi contraseña es X", "la clave del wifi es X", "password=X", "pin 4821" | `[CONTRASEÑA]` |
| Tokens y llaves de API | `Bearer ...`, `token: ...`, `sk-...`, `ghp_...`, `AKIA...` | `[TOKEN]` |
| Correos electrónicos | `nombre@dominio.cr` | `[CORREO]` |
| Cédulas de Costa Rica | `1-1234-0567`, `1 1234 0567`, `112340567`, `01-1234-0567` | `[CEDULA]` |
| Teléfonos de Costa Rica | `8888-1234`, `+506 2222 3344` | `[TELEFONO]` |
| Tarjetas de pago | Números de 13 a 19 dígitos que superan la verificación de Luhn | `[TARJETA]` |
| Direcciones IP | Privadas (10/8, 172.16/12, 192.168/16) y públicas | `[IP_INTERNA]`, `[IP]` |
| Nombres de equipo | `mail.empresa.local`, `SRV-CORREO-01` | `[HOST]` |
| Nombres de personas | El usuario y los agentes del caso; frases como "me llamo..." | "el usuario", "el agente", `[NOMBRE]` |

El sanitizador evita también los falsos positivos más comunes: no reemplaza "contraseña expirada" (no hay un valor que ocultar) ni la palabra "ping", y una prueba automática verifica que ninguno de los textos de la base de conocimiento resulte alterado. Las pruebas del sanitizador cubren 39 casos.

El prompt exacto que se envió para cada tiquete se guarda ya sanitizado y puede consultarse en `GET /tiquetes/{id}/ia`. El escenario 6 de la demostración registra un tiquete cuyo texto contiene una contraseña, una cédula y el nombre del usuario, y verifica que ninguno de esos datos aparezca en el prompt.

## Control de lo que genera la IA

La IA solo redacta. Su respuesta pasa por un validador antes de guardarse o mostrarse, que rechaza:

1. Pasos que no existen en el diagnóstico del motor.
2. Pasos fuera del orden establecido por el motor.
3. Pasos declarados pero no escritos en la guía (se verifica por palabras clave de cada paso).
4. Guías sin todos los pasos ni numeración, cuando el caso no se escala.
5. Acciones que el motor no indicó, como formatear, reinstalar, desactivar el antivirus, editar el registro, comprar equipo, usar comandos de consola o modificar la BIOS.
6. En casos escalados, guías que no informan el escalamiento o que prometen una solución inmediata.
7. Guías que tutean al usuario.
8. Notas técnicas que contradicen la prioridad o el escalamiento del motor.

Si la respuesta no pasa el validador, se reintenta una vez explicando los errores al modelo. Si vuelve a fallar, o si Ollama no responde, la guía y la nota se generan con una plantilla determinista que solo contiene información del motor. El resultado de cada caso queda registrado como `ia_ok`, `ia_reintento` o `fallback`.

## Limitaciones

- El modelo de 3 mil millones de parámetros sigue bien las reglas de contenido, pero no siempre las de formato y tono. En las pruebas con el modelo real se observaron los tres resultados posibles. Cuando el modelo falla, el usuario recibe la plantilla; el sistema no depende de que la IA acierte.
- La detección de tuteo se basa en una lista de formas verbales; una forma que no esté en la lista puede pasar el validador. Este caso afecta la redacción, no el contenido técnico de la guía.
- El sanitizador funciona con patrones. Un dato sensible con un formato no contemplado podría no detectarse; por esa razón la primera barrera excluye por completo el texto libre del usuario.
- La licencia del modelo de 3 mil millones de parámetros permite el uso académico. Un uso comercial requeriría cambiar a un modelo con licencia Apache 2.0, como `qwen2.5:7b`.
