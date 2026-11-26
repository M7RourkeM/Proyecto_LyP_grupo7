# Cambios a la base de conocimiento y al motor de inferencia

Cambios hechos para integrar el motor con el backend. Las firmas originales se conservan y las pruebas originales siguen pasando (32 de 32 en total, contando las nuevas).

## 1. Una causa es candidata si explica al menos un sintoma (`motor_inferencia.pl`, seccion 2)

Antes, una causa solo era candidata si explicaba todos los sintomas. Con `[sin_internet, vpn_caida]` en un caso individual, la unica candidata era `falla_infraestructura_red`, que se escala a redes por requerir permisos administrativos. El escenario 1 del enunciado espera cable o DHCP en primer nivel.

Ahora una causa es candidata si explica al menos un sintoma. El nuevo predicado `cobertura/3` cuenta cuantos explica y ese numero se suma al puntaje. Una causa que explica todo sigue subiendo en el ranking, pero no elimina a las causas individuales mas frecuentes. Resultado del escenario 1: `cable_desconectado`, despues `dhcp_sin_respuesta`, P3, primer nivel. En el caso colectivo (escenario 5) gana `falla_infraestructura_red` y el cable queda descartado por alcance.

## 2. Urgencia indicada por el usuario (seccion 1)

El reporte puede incluir el termino `urgencia(baja|media|alta)`. La urgencia final es la mayor entre la del servicio afectado y la indicada por el usuario: el usuario puede subirla, pero no bajarla por debajo de lo critico que es el servicio. Ese termino no se cuenta como sintoma ni impide clasificar un caso como solicitud.

## 3. SLA en horas (`base_conocimiento.pl`, seccion 6)

Se agrega `sla_horas(Prioridad, HorasRespuesta, HorasResolucion)` con los mismos tiempos de `sla/3`, expresados en horas habiles con una jornada de 8 horas. El backend lo necesita para calcular el porcentaje de cumplimiento del SLA.

## 4. Incidentes dinamicos (`base_conocimiento.pl`, seccion 9)

`incidente_previo/5` ahora es dinamico. El backend inserta los tiquetes abiertos de la base de datos antes de cada diagnostico y los retira al terminar. Los incidentes de ejemplo t100 a t104 se movieron a `datos_ejemplo.pl`, que solo cargan las pruebas. Si se quedaran en la base, Finanzas apareceria siempre con un problema masivo.

## 5. Pasos con identificador (seccion 5)

`pasos_detalle/2` devuelve `paso(Orden, Id, Texto)`, con un Id del tipo `intentos_fallidos_1`. El validador del backend usa esos identificadores para rechazar cualquier paso que la IA invente.

## 6. Regla que decidio la atencion (seccion 8)

Las reglas a) a f) pasaron a `resolucion_regla/7`, que agrega un identificador de regla al final (`escalar_seguridad`, `escalar_pasos_agotados`, `escalar_varios_usuarios`, `escalar_permisos_admin`, `primer_nivel_guia_conocida`, `escalar_sin_guia`). `resolucion_soporte/6` y `/5` siguen existiendo con la misma firma.

## 7. Campos nuevos en `diagnostico_completo/4` (seccion 9)

Se agregan `sla_horas_respuesta`, `sla_horas_resolucion`, `pasos_detalle`, `posible_problema_masivo` (si/no) y `reglas_aplicadas` (regla de tipo, `matriz_prioridad` y regla de atencion). Los campos que ya existian no cambian.

## 8. Un problema masivo se escala aunque se reporte como individual (seccion 8)

Antes, la regla c) escalaba solo si el usuario reportaba varios afectados. Si tres personas del mismo departamento reportaban la misma caida por separado, cada una como individual, el motor clasificaba el tercer caso como `problema`, pero lo dejaba en primer nivel.

Ahora `diagnostico_completo/4` decide la atencion con `decision_atencion/8`. Si `problema_masivo_reporte/3` detecta un posible problema masivo, el caso se escala al grupo especialista de la causa con la regla `escalar_problema_masivo`. La unica regla con mayor prioridad es la de seguridad (`caso_de_seguridad/2`): un posible incidente de seguridad va siempre a ciberseguridad. `resolucion_regla/7` y `resolucion_soporte/5,6` no cambian. Se agregaron 3 pruebas (32 de 32 en total).

## Pendiente de acordar

- Los departamentos de la base de datos usaran los mismos atomos que el motor (`finanzas`, `ventas`, `recursos_humanos`, ...). Si se agregan departamentos, hay que avisar.
- La bandera `requiere_permisos_admin` del tiquete no se usa: el motor lo decide por causa con `requiere_permisos_admin/1`.
