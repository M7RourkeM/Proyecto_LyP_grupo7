/* ================================================================
   Puente entre el backend y el motor de inferencia (Integrante 1).

   Recibe el tiquete en JSON (contrato 3.1), arma el reporte que espera
   diagnostico_completo/4, carga temporalmente los incidentes abiertos
   y la retroalimentacion, y devuelve el diagnostico en JSON (contrato
   3.2). Toda traduccion entre el contrato y los atomos del motor esta
   aqui, en Prolog; el backend solo transporta JSON.

   Dos formas de uso:
     - subprocess: puente_main lee JSON de stdin y escribe en stdout.
     - pyswip:     diagnostico_json(+TextoEntrada, -TextoSalida).
   ================================================================ */

:- use_module(library(http/json)).
:- use_module(library(time)).
:- use_module(library(apply)).
:- use_module(library(lists)).

% ----------------------------------------------------------------
% Puntos de entrada
% ----------------------------------------------------------------
puente_main :-
    set_stream(user_input, encoding(utf8)),
    set_stream(user_output, encoding(utf8)),
    json_read_dict(user_input, Entrada, [value_string_as(atom)]),
    procesar(Entrada, Salida),
    json_write_dict(user_output, Salida, [width(0)]),
    nl(user_output).

diagnostico_json(TextoEntrada, TextoSalida) :-
    atom_json_dict(TextoEntrada, Entrada, [value_string_as(atom)]),
    procesar(Entrada, Salida),
    atom_json_dict(TextoSalida, Salida, [as(atom), width(0)]).

% procesar(+Entrada, -Salida): nunca falla; los problemas se devuelven
% como _{error: Codigo, detalle: Texto}.
procesar(Entrada, Salida) :-
    get_dict(timeout_s, Entrada, Limite),
    catch(call_with_time_limit(Limite, diagnosticar(Entrada, Salida0)),
          Error, error_a_json(Error, Salida0)),
    !,
    Salida = Salida0.
procesar(_, _{error: sin_resultado,
              detalle: 'El motor no produjo un diagnostico'}).

error_a_json(time_limit_exceeded, _{error: timeout,
                                    detalle: 'El motor excedio el tiempo limite'}) :- !.
error_a_json(error(existence_error(procedure, PI), _), _{error: predicado_inexistente,
                                                        detalle: Texto}) :- !,
    format(atom(Texto), 'La base de conocimiento no define ~w', [PI]).
error_a_json(entrada_invalida(Desconocidos), _{error: entrada_invalida,
                                               detalle: Texto,
                                               desconocidos: Desconocidos}) :- !,
    atomic_list_concat(Desconocidos, ', ', Lista),
    format(atom(Texto), 'Datos que el motor no reconoce: ~w', [Lista]).
error_a_json(Error, _{error: error_prolog, detalle: Texto}) :-
    message_to_codes(Error, Texto).

message_to_codes(Error, Texto) :-
    catch(message_to_codes(Error, _, Codes), _, fail), !,
    atom_codes(Texto, Codes).
message_to_codes(Error, Texto) :-
    format(atom(Texto), '~q', [Error]).

% ----------------------------------------------------------------
% Diagnostico con datos temporales
% Los incidentes abiertos y la retroalimentacion se agregan solo para
% esta consulta y se retiran siempre, aunque ocurra un error.
% ----------------------------------------------------------------
diagnosticar(Entrada, Salida) :-
    armar_reporte(Entrada, Reporte),
    Departamento = Entrada.departamento,
    length(Entrada.pasos_ya_aplicados, Aplicados),
    setup_call_cleanup(
        cargar_temporales(Entrada),
        diagnostico_completo(Reporte, Departamento, Aplicados, D),
        retirar_temporales),
    !,
    armar_salida(Reporte, D, Salida).

cargar_temporales(Entrada) :-
    retirar_temporales,
    forall(member(I, Entrada.incidentes_abiertos), cargar_incidente(I)),
    forall(member(R, Entrada.resultados_previos), cargar_resultado(R)).

cargar_incidente(I) :-
    forall(( member(S, I.sintomas), sintoma(S, Componente, _) ),
           assertz(incidente_previo(I.id, Componente, S, I.departamento, I.estado))).

cargar_resultado(R) :-
    ( R.funciono == true -> Valor = si ; Valor = no ),
    assertz(resultado_solucion(R.causa, Valor)).

retirar_temporales :-
    retractall(incidente_previo(_, _, _, _, _)),
    retractall(resultado_solucion(_, _)).

% ----------------------------------------------------------------
% Del contrato 3.1 al reporte del motor
% ----------------------------------------------------------------
armar_reporte(Entrada, Reporte) :-
    Sintomas = Entrada.sintomas,
    exclude(dato_conocido, Sintomas, Desconocidos),
    (   Desconocidos == [] -> true
    ;   throw(entrada_invalida(Desconocidos))
    ),
    contexto_por_alcance(Entrada.alcance, Contexto),
    evidencia_por_componente(Entrada.componente, Evidencia),
    ( Entrada.sospecha_seguridad == true -> Seguridad = [sospecha_seguridad] ; Seguridad = [] ),
    append([Sintomas, Contexto, Evidencia, Seguridad, [urgencia(Entrada.urgencia)]], Reporte0),
    list_to_set(Reporte0, Reporte).

dato_conocido(D) :- sintoma(D, _, _), !.
dato_conocido(D) :- peticion(D, _, _), !.
dato_conocido(D) :- contexto(D, _, _), !.
dato_conocido(D) :- evidencia(D, _).

% El alcance del contrato se expresa con los datos de contexto del motor.
contexto_por_alcance(individual, []).
contexto_por_alcance(departamento, [varios_usuarios_afectados]).
contexto_por_alcance(organizacion, [toda_organizacion_afectada]).

% El tipo de conexion es una evidencia que permite descartar causas.
evidencia_por_componente(red_cableada, [usa_cable]) :- !.
evidencia_por_componente(red_inalambrica, [usa_wifi]) :- !.
evidencia_por_componente(_, []).

% ----------------------------------------------------------------
% De la salida del motor al contrato 3.2
% ----------------------------------------------------------------
armar_salida(Reporte, D, Salida) :-
    valor(D, causa, Causa),
    valor(D, otras_causas, Otras),
    lista_causas(Causa, Otras, Causas),
    valor(D, causas_descartadas, Descartadas0),
    maplist(descartada_json, Descartadas0, Descartadas),
    valor(D, nivel, NivelAtomo), nivel_numero(NivelAtomo, Nivel),
    valor(D, motivo, Motivo),
    ( Nivel > 1 -> Escalar = true, MotivoEsc = Motivo ; Escalar = false, MotivoEsc = null ),
    valor(D, pasos_detalle, Pasos0),
    maplist(paso_json, Pasos0, Pasos),
    valor(D, posible_problema_masivo, Masivo0), si_no_bool(Masivo0, Masivo),
    categoria(Reporte, Categoria),
    copiar_valores(D, [tipo-tipo_registro, impacto-impacto, urgencia-urgencia,
                       prioridad-prioridad, sla_horas_resolucion-sla_horas,
                       sla_horas_respuesta-sla_horas_respuesta, grupo-grupo_resolutor,
                       incidentes_relacionados-incidentes_relacionados,
                       reglas_aplicadas-reglas_aplicadas], Copiados),
    dict_pairs(Base, _, Copiados),
    Salida = Base.put(_{
        causas: Causas,
        causas_descartadas: Descartadas,
        categoria: Categoria,
        pasos: Pasos,
        escalar: Escalar,
        nivel: Nivel,
        motivo: Motivo,
        motivo_escalamiento: MotivoEsc,
        posible_problema_masivo: Masivo
    }).

% La salida del motor es una lista Clave=Valor.
valor(D, Clave, Valor) :- memberchk(Clave = Valor, D).

% copiar_valores(+D, +[ClaveMotor-ClaveContrato], -[ClaveContrato-Valor])
copiar_valores(_, [], []).
copiar_valores(D, [Motor-Contrato | Resto], [Contrato-Valor | Copiados]) :-
    valor(D, Motor, Valor),
    copiar_valores(D, Resto, Copiados).

lista_causas(Causa, _, []) :- memberchk(Causa, [no_aplica, sin_determinar]), !.
lista_causas(Causa, Otras, Causas) :-
    maplist(causa_json, [Causa | Otras], Causas).

causa_json(C, _{id: C, descripcion: Desc}) :- causa(C, Desc).
descartada_json(C-Motivo, _{id: C, motivo: Motivo}).
paso_json(paso(Orden, Id, Texto), _{orden: Orden, id: Id, texto: Texto}).

nivel_numero(primer_nivel, 1).
nivel_numero(segundo_nivel, 2).
nivel_numero(tercer_nivel, 3).

si_no_bool(si, true).
si_no_bool(no, false).

% Categoria: servicio del primer sintoma tecnico; solicitud si es peticion.
categoria(Reporte, Categoria) :-
    member(S, Reporte), sintoma(S, Categoria, _), !.
categoria(Reporte, solicitud) :-
    member(S, Reporte), peticion(S, _, _), !.
categoria(_, sin_categoria).
