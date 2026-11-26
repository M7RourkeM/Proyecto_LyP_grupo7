/* ================================================================
   Proyecto: Asistente Inteligente de Diagnostico y Soporte de TI
   Integrante 1 - Motor de inferencia

   Cargar este archivo desde la misma carpeta que
   base_conocimiento.pl. Ejemplo en SWI-Prolog:
       ?- [motor_inferencia].

   Un reporte es una lista que puede mezclar:
     - sintomas tecnicos   (sin_internet, no_imprime, ...)
     - datos de contexto   (companeros_sin_internet, ...)
     - evidencias          (usa_wifi, sospecha_seguridad, ...)
     - peticiones          (instalar_software, ...)
   El motor separa cada tipo de dato y lo usa para un fin distinto.
   ================================================================ */

:- consult('base_conocimiento.pl').

% Retroalimentacion: la aplicacion registra si la solucion funciono.
% resultado_solucion(Causa, si | no).
:- dynamic resultado_solucion/2.

% ----------------------------------------------------------------
% 0. Utilidades recursivas
% ----------------------------------------------------------------
contar_elementos([], 0).
contar_elementos([_ | Resto], Total) :-
    contar_elementos(Resto, Parcial),
    Total is Parcial + 1.

maximo([X], X).
maximo([X | Resto], Maximo) :-
    Resto \== [],
    maximo(Resto, MaximoResto),
    Maximo is max(X, MaximoResto).

% ----------------------------------------------------------------
% 1. Separar los datos del reporte
% ----------------------------------------------------------------
no_tecnico(Dato) :- contexto(Dato, _, _).
no_tecnico(Dato) :- evidencia(Dato, _).
no_tecnico(Dato) :- peticion(Dato, _, _).
no_tecnico(Dato) :- es_urgencia_reportada(Dato).

% urgencia(U) en el reporte es la urgencia indicada por el usuario.
es_urgencia_reportada(urgencia(_)).

sintomas_tecnicos(Reporte, Sintomas) :-
    exclude(no_tecnico, Reporte, Sintomas).

% El impacto se infiere del contexto; si no hay contexto es individual.
impacto_reporte(Reporte, organizacion) :-
    member(Dato, Reporte), contexto(Dato, organizacion, _), !.
impacto_reporte(Reporte, departamento) :-
    member(Dato, Reporte), contexto(Dato, departamento, _), !.
impacto_reporte(_, individual).

% La urgencia es la mayor entre los servicios afectados y la que
% indico el usuario. El usuario puede subir la urgencia, pero no
% bajarla por debajo de lo critico que es el servicio.
urgencia_reporte(Reporte, alta) :-
    member(sospecha_seguridad, Reporte), !.
urgencia_reporte(Reporte, Urgencia) :-
    sintomas_tecnicos(Reporte, Sintomas),
    findall(Valor,
        (   member(S, Sintomas), sintoma(S, Componente, _),
            urgencia_componente(Componente, U), nivel_urgencia(U, Valor)
        ;   member(urgencia(U), Reporte), nivel_urgencia(U, Valor)
        ),
        Valores),
    (   Valores == []
    ->  Urgencia = baja
    ;   maximo(Valores, Max), nivel_urgencia(Urgencia, Max)
    ).

% ----------------------------------------------------------------
% 2. Diagnostico a partir de varios sintomas
% Una causa es candidata cuando explica AL MENOS UNO de los sintomas
% tecnicos y ninguna evidencia ni el alcance del caso la descartan.
% Las causas que explican mas sintomas reciben mas puntaje
% (seccion 3), asi que una causa que lo explica todo sube en el
% ranking, pero no elimina a las causas individuales mas comunes.
% ----------------------------------------------------------------
explica_sintomas(Causa, Reporte) :-
    causa(Causa, _),
    cobertura(Causa, Reporte, Cantidad),
    Cantidad > 0.

% cobertura(+Causa, +Reporte, -Cantidad): sintomas que explica.
cobertura(Causa, Reporte, Cantidad) :-
    sintomas_tecnicos(Reporte, Sintomas),
    include(causa_sintoma(Causa), Sintomas, Explicados),
    contar_elementos(Explicados, Cantidad).

% Descarte por evidencia contradictoria (ej. cable con Wi-Fi).
motivo_descarte(Causa, Reporte, Motivo) :-
    incompatibilidad(Causa, Evidencia),
    member(Evidencia, Reporte),
    format(atom(Motivo), 'Se descarta porque el reporte indica ~w', [Evidencia]).
% Descarte por alcance: una causa individual no explica una falla
% que afecta a varios usuarios.
motivo_descarte(Causa, Reporte, 'Se descarta porque solo afecta a un usuario y el caso es colectivo') :-
    alcance_causa(Causa, individual),
    impacto_reporte(Reporte, Impacto),
    Impacto \== individual.

causa_descartada(Causa, Reporte) :-
    motivo_descarte(Causa, Reporte, _), !.

causa_compatible(Causa, Reporte) :-
    explica_sintomas(Causa, Reporte),
    \+ causa_descartada(Causa, Reporte).

causas_descartadas(Reporte, Descartadas) :-
    findall(Causa-Motivo,
        (explica_sintomas(Causa, Reporte),
         once(motivo_descarte(Causa, Reporte, Motivo))),
        Descartadas).

% ----------------------------------------------------------------
% 3. Ordenar las causas de la mas probable a la menos probable
% Puntaje = frecuencia (peso) + ajuste por alcance
%           + sintomas explicados + retroalimentacion.
% ----------------------------------------------------------------
ajuste_alcance(individual, individual, 2).
ajuste_alcance(individual, ambos, 1).
ajuste_alcance(individual, colectivo, 0).
ajuste_alcance(Impacto, colectivo, 2) :- Impacto \== individual.
ajuste_alcance(Impacto, ambos, 1) :- Impacto \== individual.

ajuste_historial(Causa, Ajuste) :-
    aggregate_all(count, resultado_solucion(Causa, si), Exitos),
    aggregate_all(count, resultado_solucion(Causa, no), Fallos),
    Ajuste is Exitos - Fallos.

puntaje(Causa, Reporte, Puntaje) :-
    peso(Causa, Peso),
    impacto_reporte(Reporte, Impacto),
    alcance_causa(Causa, Alcance),
    ajuste_alcance(Impacto, Alcance, Ajuste),
    cobertura(Causa, Reporte, Cobertura),
    ajuste_historial(Causa, Historial),
    Puntaje is Peso + Ajuste + Cobertura + Historial.

causas_probables(Reporte, Causas) :-
    findall(Puntaje-Causa,
        (causa_compatible(Causa, Reporte), puntaje(Causa, Reporte, Puntaje)),
        Pares),
    sort(1, @>=, Pares, Ordenados),
    pairs_values(Ordenados, Causas).

% Una causa a la vez mediante backtracking (pulsar ; en la consola).
causa_probable(Reporte, Causa) :-
    causas_probables(Reporte, Causas),
    member(Causa, Causas).

% Registro de retroalimentacion desde la aplicacion.
registrar_resultado(Causa, Funciono) :-
    memberchk(Funciono, [si, no]),
    assertz(resultado_solucion(Causa, Funciono)).

% ----------------------------------------------------------------
% 4. Prioridad y SLA
% ----------------------------------------------------------------
prioridad_y_sla(Impacto, Urgencia, Prioridad, Respuesta, Resolucion) :-
    matriz_prioridad(Impacto, Urgencia, Prioridad),
    sla(Prioridad, Respuesta, Resolucion).

% Version que infiere impacto y urgencia desde el reporte.
prioridad_reporte(Reporte, Impacto, Urgencia, Prioridad, Respuesta, Resolucion) :-
    impacto_reporte(Reporte, Impacto),
    urgencia_reporte(Reporte, Urgencia),
    prioridad_y_sla(Impacto, Urgencia, Prioridad, Respuesta, Resolucion).

% ----------------------------------------------------------------
% 5. Pasos de solucion en el orden establecido
% ----------------------------------------------------------------
pasos_solucion(Causa, Pasos) :-
    findall(Orden-Paso, solucion(Causa, Orden, Paso), Pares),
    keysort(Pares, ParesOrdenados),
    extraer_pasos(ParesOrdenados, Pasos).

extraer_pasos([], []).
extraer_pasos([_Orden-Paso | Resto], [Paso | Pasos]) :-
    extraer_pasos(Resto, Pasos).

% pasos_detalle(+Causa, -Lista): cada paso como paso(Orden, Id, Texto).
% El Id (causa_orden) permite que la aplicacion verifique que la IA
% solo menciona pasos que salieron de esta base de conocimiento.
pasos_detalle(Causa, Detalle) :-
    findall(Orden-Texto, solucion(Causa, Orden, Texto), Pares),
    keysort(Pares, Ordenados),
    findall(paso(Orden, Id, Texto),
        ( member(Orden-Texto, Ordenados),
          atomic_list_concat([Causa, Orden], '_', Id) ),
        Detalle).

total_pasos(Causa, Total) :-
    pasos_solucion(Causa, Pasos),
    contar_elementos(Pasos, Total).

% ----------------------------------------------------------------
% 6. Correlacion de incidentes similares
% ----------------------------------------------------------------
incidentes_del_area(Componente, Departamento, IDs) :-
    findall(ID,
        (incidente_previo(ID, Componente, _Sintoma, Departamento, Estado),
         Estado \= cerrado),
        IDs).

posible_problema_masivo(Componente, Departamento, Cantidad) :-
    incidentes_del_area(Componente, Departamento, IDs),
    contar_elementos(IDs, Cantidad),
    Cantidad >= 2.

incidentes_relacionados(Reporte, Departamento, IDs) :-
    sintomas_tecnicos(Reporte, Sintomas),
    findall(ID,
        (member(S, Sintomas), sintoma(S, Componente, _),
         incidente_previo(ID, Componente, _, Departamento, Estado),
         Estado \= cerrado),
        Lista),
    sort(Lista, IDs).

% ----------------------------------------------------------------
% 7. Clasificacion del registro
% ----------------------------------------------------------------
% Version simple, por naturaleza y recurrencia.
clasificar_registro(solicitud, _Recurrente, solicitud_servicio) :- !.
clasificar_registro(interrupcion, si, problema) :- !.
clasificar_registro(interrupcion, no, incidente).

% Version con criterios, a partir del reporte completo.
clasificar_caso(Reporte, _Departamento, solicitud_servicio) :-
    exclude(es_urgencia_reportada, Reporte, Datos),
    Datos \== [],
    forall(member(Dato, Datos), peticion(Dato, _, _)), !.
clasificar_caso(Reporte, Departamento, problema) :-
    sintomas_tecnicos(Reporte, Sintomas),
    member(S, Sintomas), sintoma(S, Componente, _),
    posible_problema_masivo(Componente, Departamento, _), !.
clasificar_caso(_, _, incidente).

% ----------------------------------------------------------------
% 8. Decision de atencion y escalamiento
% Las reglas se evaluan en orden; la primera que se cumple decide.
% El nivel siempre se toma del grupo resolutor, para que nunca haya
% contradicciones entre el grupo y su nivel.
% ----------------------------------------------------------------
nivel_de_grupo(Grupo, Nivel) :-
    grupo_resolutor(Grupo, Nivel, _).

escalar_a(Causa, Grupo, Nivel) :-
    requiere_grupo(Causa, Grupo),
    nivel_de_grupo(Grupo, Nivel).

% El ultimo argumento identifica la regla que decidio; la aplicacion
% lo guarda en reglas_aplicadas para justificar la decision.
% a) Sospecha de incidente de seguridad.
resolucion_regla(Causa, Reporte, _Aplicados, tercer_nivel, ciberseguridad,
                 'Posible incidente de seguridad; requiere revision especializada',
                 escalar_seguridad) :-
    (Causa == certificado_vencido ; member(sospecha_seguridad, Reporte)), !.
% b) Pasos de solucion agotados.
resolucion_regla(Causa, _Reporte, Aplicados, Nivel, Grupo,
                 'Se aplicaron todos los pasos de primer nivel sin resolver el caso',
                 escalar_pasos_agotados) :-
    total_pasos(Causa, Total),
    Aplicados >= Total, !,
    escalar_a(Causa, Grupo, Nivel).
% c) Varios usuarios afectados (posible falla masiva).
resolucion_regla(Causa, Reporte, _Aplicados, Nivel, Grupo,
                 'Hay varios usuarios afectados; posible falla masiva',
                 escalar_varios_usuarios) :-
    impacto_reporte(Reporte, Impacto),
    Impacto \== individual, !,
    escalar_a(Causa, Grupo, Nivel).
% d) La solucion necesita permisos administrativos.
resolucion_regla(Causa, _Reporte, _Aplicados, Nivel, Grupo,
                 'La solucion requiere permisos administrativos',
                 escalar_permisos_admin) :-
    requiere_permisos_admin(Causa), !,
    escalar_a(Causa, Grupo, Nivel).
% e) Existe una guia que la mesa de ayuda puede aplicar.
resolucion_regla(Causa, _Reporte, _Aplicados, primer_nivel, mesa_ayuda,
                 'Existe una guia conocida que puede aplicar la mesa de ayuda',
                 primer_nivel_guia_conocida) :-
    solucion(Causa, _, _), !.
% f) No hay guia registrada.
resolucion_regla(Causa, _Reporte, _Aplicados, Nivel, Grupo,
                 'No existe una solucion de primer nivel registrada',
                 escalar_sin_guia) :-
    escalar_a(Causa, Grupo, Nivel).

% Version sin identificador de regla (se conserva la firma original).
resolucion_soporte(Causa, Reporte, Aplicados, Nivel, Grupo, Motivo) :-
    resolucion_regla(Causa, Reporte, Aplicados, Nivel, Grupo, Motivo, _).

% Version corta: el caso aun no tiene pasos aplicados.
resolucion_soporte(Causa, Reporte, Nivel, Grupo, Motivo) :-
    resolucion_soporte(Causa, Reporte, 0, Nivel, Grupo, Motivo).

% Grupo cuando no se encontro causa o el caso es una peticion.
grupo_sin_causa(Reporte, Grupo) :-
    member(Dato, Reporte), peticion(Dato, Grupo, _), !.
grupo_sin_causa(Reporte, Grupo) :-
    sintomas_tecnicos(Reporte, [S | _]), sintoma(S, Componente, _),
    grupo_por_componente(Componente, Grupo), !.
grupo_sin_causa(_, mesa_ayuda).

% ----------------------------------------------------------------
% 9. Consulta completa
% diagnostico_completo(+Reporte, +Departamento, +PasosAplicados, -Diagnostico)
% Diagnostico es una lista Clave=Valor, facil de convertir a JSON
% desde la aplicacion (Python/Java) para enviarla a la IA.
% ----------------------------------------------------------------
diagnostico_completo(Reporte, Departamento, Aplicados,
        [ tipo = Tipo,
          causa = Causa,
          otras_causas = Otras,
          causas_descartadas = Descartadas,
          impacto = Impacto,
          urgencia = Urgencia,
          prioridad = Prioridad,
          sla_respuesta = Respuesta,
          sla_resolucion = Resolucion,
          sla_horas_respuesta = HorasRespuesta,
          sla_horas_resolucion = HorasResolucion,
          pasos = Pasos,
          pasos_detalle = Detalle,
          nivel = Nivel,
          grupo = Grupo,
          motivo = Motivo,
          posible_problema_masivo = Masivo,
          incidentes_relacionados = Relacionados,
          reglas_aplicadas = [ReglaTipo, matriz_prioridad, ReglaAtencion] ]) :-
    clasificar_caso(Reporte, Departamento, Tipo),
    regla_tipo(Tipo, ReglaTipo),
    causas_probables(Reporte, Causas),
    causas_descartadas(Reporte, Descartadas),
    prioridad_reporte(Reporte, Impacto, Urgencia, Prioridad, Respuesta, Resolucion),
    sla_horas(Prioridad, HorasRespuesta, HorasResolucion),
    incidentes_relacionados(Reporte, Departamento, Relacionados),
    problema_masivo_reporte(Reporte, Departamento, Masivo),
    (   Causas = [Causa | Otras]
    ->  pasos_solucion(Causa, Pasos),
        pasos_detalle(Causa, Detalle),
        resolucion_regla(Causa, Reporte, Aplicados, Nivel, Grupo, Motivo, ReglaAtencion)
    ;   Tipo == solicitud_servicio
    ->  Causa = no_aplica, Otras = [], Pasos = [], Detalle = [],
        grupo_sin_causa(Reporte, Grupo), nivel_de_grupo(Grupo, Nivel),
        Motivo = 'Peticion estandar de servicio',
        ReglaAtencion = solicitud_estandar
    ;   Causa = sin_determinar, Otras = [], Pasos = [], Detalle = [],
        grupo_sin_causa(Reporte, Grupo), nivel_de_grupo(Grupo, Nivel),
        Motivo = 'No se encontro una causa registrada para los sintomas',
        ReglaAtencion = sin_regla_aplicable
    ).

% Identificador de la regla que decidio el tipo de registro.
regla_tipo(solicitud_servicio, tipo_solicitud_estandar).
regla_tipo(problema, tipo_problema_masivo).
regla_tipo(incidente, tipo_incidente).

% problema_masivo_reporte(+Reporte, +Departamento, -si|no).
problema_masivo_reporte(Reporte, Departamento, si) :-
    sintomas_tecnicos(Reporte, Sintomas),
    member(S, Sintomas), sintoma(S, Componente, _),
    posible_problema_masivo(Componente, Departamento, _), !.
problema_masivo_reporte(_, _, no).
