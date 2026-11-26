/* ================================================================
   Incidentes de ejemplo para las pruebas en consola.
   La aplicacion NO carga este archivo: en produccion los incidentes
   abiertos se insertan desde la base de datos.
   ================================================================ */

cargar_datos_ejemplo :-
    retractall(incidente_previo(_, _, _, _, _)),
    assertz(incidente_previo(t100, correo, no_recibe_correos, finanzas, abierto)),
    assertz(incidente_previo(t101, correo, no_envia_correos, finanzas, abierto)),
    assertz(incidente_previo(t102, correo, no_recibe_correos, recursos_humanos, en_atencion)),
    assertz(incidente_previo(t103, red, sin_internet, ventas, cerrado)),
    assertz(incidente_previo(t104, cuentas, cuenta_bloqueada, ventas, cerrado)).

:- initialization(cargar_datos_ejemplo).
