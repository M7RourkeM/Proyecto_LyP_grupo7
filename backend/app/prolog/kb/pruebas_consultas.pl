/* ================================================================
   Archivo de pruebas para el motor de inferencia.
   Abrir SWI-Prolog en esta carpeta y ejecutar:
       ?- [pruebas_consultas].
       ?- correr_pruebas.

   Tambien se pueden copiar las consultas de cada prueba y
   ejecutarlas una por una en la consola.
   ================================================================ */

:- consult('motor_inferencia.pl').
:- consult('datos_ejemplo.pl').

% prueba(Nombre, Consulta): la consulta debe tener exito.
% --- Consultas obligatorias del enunciado -------------------------

% 1. Sin Internet, VPN caida y companeros con el mismo sintoma.
% Con varios usuarios afectados, la falla de infraestructura es la
% mas probable y el cable (causa individual) queda descartado.
prueba('Consulta 1: causas de sin internet + VPN + companeros',
    ( causas_probables([sin_internet, vpn_caida, companeros_sin_internet],
                       [falla_infraestructura_red | _]),
      causas_descartadas([sin_internet, vpn_caida, companeros_sin_internet], D),
      memberchk(cable_desconectado-_, D) )).

% 2. Caida del correo que afecta a todo un departamento.
prueba('Consulta 2: prioridad y SLA (departamento, urgencia alta)',
    prioridad_y_sla(departamento, alta, p1, '15 minutos', '4 horas')).
prueba('Consulta 2b: prioridad inferida desde el reporte de correo',
    prioridad_reporte([no_recibe_correos, varios_usuarios_afectados],
                      departamento, alta, p1, _, _)).

% 3. Pasos para una cuenta bloqueada, en orden.
prueba('Consulta 3: pasos ordenados para cuenta bloqueada',
    ( pasos_solucion(intentos_fallidos, Pasos),
      contar_elementos(Pasos, 4),
      Pasos = ['Confirmar la identidad del usuario mediante el procedimiento institucional' | _] )).

% 4. Primer nivel o escalamiento.
prueba('Consulta 4: falla de red del departamento se escala a redes',
    resolucion_soporte(falla_infraestructura_red,
        [sin_internet, vpn_caida, companeros_sin_internet],
        segundo_nivel, redes, _)).

% --- Escenarios de validacion del enunciado ------------------------

prueba('Escenario: usuario sin internet -> cable, primer nivel',
    ( causas_probables([sin_internet], [cable_desconectado | _]),
      resolucion_soporte(cable_desconectado, [sin_internet], primer_nivel, mesa_ayuda, _) )).

prueba('Escenario: correo caido en un departamento -> servidor, infraestructura',
    ( causas_probables([no_recibe_correos, varios_usuarios_afectados], [correo_servidor_caido]),
      resolucion_soporte(correo_servidor_caido, [no_recibe_correos, varios_usuarios_afectados],
                         segundo_nivel, infraestructura, _) )).

prueba('Escenario: cuenta bloqueada -> se resuelve en primer nivel',
    ( causas_probables([cuenta_bloqueada], [intentos_fallidos]),
      resolucion_soporte(intentos_fallidos, [cuenta_bloqueada], primer_nivel, mesa_ayuda, _) )).

prueba('Escenario: impresora de red sin servicio -> cola detenida, soporte de equipos',
    ( causas_probables([no_imprime, varios_usuarios_afectados], [cola_impresion_detenida]),
      resolucion_soporte(cola_impresion_detenida, [no_imprime, varios_usuarios_afectados],
                         segundo_nivel, soporte_equipos, _) )).

% --- Descarte, seguridad, escalamiento y correlacion ---------------

prueba('Descarte por alcance: cable desconectado con companeros afectados',
    causa_descartada(cable_desconectado, [sin_internet, companeros_sin_internet])).

prueba('Descarte por evidencia: usa Wi-Fi descarta el cable',
    ( causa_descartada(cable_desconectado, [sin_internet, usa_wifi]),
      causas_probables([sin_internet, usa_wifi], Causas),
      \+ member(cable_desconectado, Causas) )).

prueba('Seguridad: certificado vencido va a tercer nivel',
    resolucion_soporte(certificado_vencido, [vpn_caida], tercer_nivel, ciberseguridad, _)).

prueba('Seguridad: la sospecha de seguridad escala cualquier caso',
    resolucion_soporte(intentos_fallidos, [cuenta_bloqueada, sospecha_seguridad],
                       tercer_nivel, ciberseguridad, _)).

prueba('Pasos agotados: cuenta bloqueada con 4 pasos aplicados se escala',
    resolucion_soporte(intentos_fallidos, [cuenta_bloqueada], 4,
                       segundo_nivel, cuentas_y_accesos, _)).

prueba('Permisos administrativos: controlador de impresora se escala',
    resolucion_soporte(controlador_impresora, [no_imprime],
                       segundo_nivel, soporte_equipos, _)).

prueba('Correlacion: dos incidentes abiertos de correo en Finanzas',
    posible_problema_masivo(correo, finanzas, 2)).

prueba('Clasificacion: correo en Finanzas se registra como problema',
    clasificar_caso([no_recibe_correos], finanzas, problema)).

prueba('Clasificacion: una peticion es solicitud de servicio',
    clasificar_caso([instalar_software], ventas, solicitud_servicio)).

prueba('Clasificacion simple: interrupcion recurrente tiene una sola respuesta',
    findall(T, clasificar_registro(interrupcion, si, T), [problema])).

prueba('Diagnostico completo de una caida de correo en Finanzas',
    ( diagnostico_completo([no_recibe_correos, varios_usuarios_afectados], finanzas, 0, D),
      memberchk(causa = correo_servidor_caido, D),
      memberchk(prioridad = p1, D),
      memberchk(grupo = infraestructura, D),
      memberchk(incidentes_relacionados = [t100, t101], D) )).

% --- Pruebas de los cambios para integrar con el backend ----------

prueba('Escenario 1: sin internet + VPN individual -> cable y DHCP, P3, primer nivel',
    ( diagnostico_completo([sin_internet, vpn_caida], ventas, 0, D),
      memberchk(causa = cable_desconectado, D),
      memberchk(otras_causas = [dhcp_sin_respuesta | _], D),
      memberchk(prioridad = p3, D),
      memberchk(nivel = primer_nivel, D) )).

prueba('Escenario 5: masivo de red en Ventas -> problema, redes, cable descartado',
    ( retractall(incidente_previo(_, _, _, _, _)),
      assertz(incidente_previo(t200, red, sin_internet, ventas, abierto)),
      assertz(incidente_previo(t201, red, sin_internet, ventas, abierto)),
      assertz(incidente_previo(t202, vpn, vpn_caida, ventas, abierto)),
      diagnostico_completo([sin_internet, vpn_caida, companeros_sin_internet], ventas, 0, D),
      cargar_datos_ejemplo,
      memberchk(tipo = problema, D),
      memberchk(posible_problema_masivo = si, D),
      memberchk(grupo = redes, D),
      memberchk(causas_descartadas = Desc, D),
      memberchk(cable_desconectado-_, Desc) )).

prueba('Urgencia: el usuario puede subir la urgencia de la impresora',
    urgencia_reporte([no_imprime, urgencia(alta)], alta)).

prueba('Urgencia: el usuario no puede bajar la urgencia del correo',
    urgencia_reporte([no_recibe_correos, urgencia(baja)], alta)).

prueba('Urgencia reportada no convierte el caso en solicitud ni en sintoma',
    ( clasificar_caso([instalar_software, urgencia(media)], ventas, solicitud_servicio),
      sintomas_tecnicos([no_imprime, urgencia(alta)], [no_imprime]) )).

prueba('SLA numerico en horas habiles',
    ( diagnostico_completo([cuenta_bloqueada], ventas, 0, D),
      memberchk(sla_horas_respuesta = 4, D),
      memberchk(sla_horas_resolucion = 16, D) )).

prueba('Pasos con identificador y orden',
    ( pasos_detalle(intentos_fallidos, Detalle),
      Detalle = [paso(1, intentos_fallidos_1, _), paso(2, intentos_fallidos_2, _) | _] )).

prueba('Reglas aplicadas en el diagnostico',
    ( diagnostico_completo([no_recibe_correos, varios_usuarios_afectados], finanzas, 0, D),
      memberchk(reglas_aplicadas = [tipo_problema_masivo, matriz_prioridad, escalar_problema_masivo], D) )).

prueba('Sin incidentes cargados no hay problema masivo',
    ( retractall(incidente_previo(_, _, _, _, _)),
      diagnostico_completo([no_recibe_correos], finanzas, 0, D),
      cargar_datos_ejemplo,
      memberchk(tipo = incidente, D),
      memberchk(posible_problema_masivo = no, D) )).

prueba('Problema masivo reportado como individual se escala al especialista',
    ( diagnostico_completo([no_recibe_correos], finanzas, 0, D),
      memberchk(tipo = problema, D),
      memberchk(nivel = segundo_nivel, D),
      memberchk(grupo = infraestructura, D),
      memberchk(reglas_aplicadas = [_, _, escalar_problema_masivo], D) )).

prueba('Sin problema masivo, el caso individual sigue en primer nivel',
    ( retractall(incidente_previo(_, _, _, _, _)),
      diagnostico_completo([cuenta_bloqueada], finanzas, 0, D),
      cargar_datos_ejemplo,
      memberchk(nivel = primer_nivel, D) )).

prueba('La seguridad tiene prioridad sobre el problema masivo',
    ( diagnostico_completo([no_recibe_correos, sospecha_seguridad], finanzas, 0, D),
      memberchk(grupo = ciberseguridad, D),
      memberchk(reglas_aplicadas = [_, _, escalar_seguridad], D) )).

% ----------------------------------------------------------------
% Ejecutar todas las pruebas y mostrar el resultado
% ----------------------------------------------------------------
correr_pruebas :-
    findall(N-C, prueba(N, C), Pruebas),
    correr(Pruebas, 0, 0).

correr([], Ok, Fallo) :-
    Total is Ok + Fallo,
    format('~nResultado: ~w de ~w pruebas correctas.~n', [Ok, Total]).
correr([Nombre-Consulta | Resto], Ok, Fallo) :-
    (   catch(once(Consulta), _, fail)
    ->  format('[OK]    ~w~n', [Nombre]), Ok1 is Ok + 1, Fallo1 = Fallo
    ;   format('[FALLA] ~w~n', [Nombre]), Ok1 = Ok, Fallo1 is Fallo + 1
    ),
    correr(Resto, Ok1, Fallo1).

% Ejemplo para ver el diagnostico completo en la consola:
% ?- diagnostico_completo([no_recibe_correos, varios_usuarios_afectados],
%                         finanzas, 0, D), print_term(D, []).
