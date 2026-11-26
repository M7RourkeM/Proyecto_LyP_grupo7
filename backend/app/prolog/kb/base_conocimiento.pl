/* ================================================================
   Proyecto: Asistente Inteligente de Diagnostico y Soporte de TI
   Integrante 1 - Base de conocimiento
   Compatible con SWI-Prolog.

   Este archivo contiene los hechos del dominio: servicios, sintomas,
   contexto del reporte, causas, soluciones, matriz de prioridad,
   tipos de registro y grupos resolutores. Los tiempos SLA son valores
   de referencia definidos para este proyecto academico; no
   representan una tabla universal.
   ================================================================ */

% ----------------------------------------------------------------
% 1. Servicios y componentes tecnologicos
% servicio(Servicio, Descripcion).
% parte_de(Subcomponente, Servicio).
% ----------------------------------------------------------------
servicio(red, 'Conectividad de red de la organizacion').
servicio(vpn, 'Acceso remoto seguro a la red institucional').
servicio(correo, 'Servicio de correo electronico').
servicio(sistema_operativo, 'Sistema operativo de los equipos').
servicio(cuentas, 'Cuentas de usuario y contrasenas').
servicio(impresoras, 'Impresoras locales y de red').
servicio(apps_negocio, 'Aplicaciones utilizadas por las areas de negocio').
servicio(nube, 'Almacenamiento y servicios en la nube').

parte_de(red_cableada, red).
parte_de(red_inalambrica, red).

% ----------------------------------------------------------------
% 2. Sintomas tecnicos y componente relacionado
% sintoma(Sintoma, Componente, Descripcion).
% Solo se registran aqui los fallos observables. El alcance
% (cuantos usuarios estan afectados) se modela aparte, en la
% seccion 3, porque no es un sintoma sino el contexto del reporte.
% ----------------------------------------------------------------
sintoma(sin_internet, red, 'El equipo no logra navegar por Internet').
sintoma(red_lenta, red, 'La conexion presenta lentitud').
sintoma(vpn_caida, vpn, 'No se logra establecer la conexion VPN').
sintoma(no_recibe_correos, correo, 'El usuario no recibe mensajes').
sintoma(no_envia_correos, correo, 'El usuario no puede enviar mensajes').
sintoma(pantalla_azul, sistema_operativo, 'El equipo muestra una pantalla azul').
sintoma(equipo_lento, sistema_operativo, 'El equipo responde lentamente').
sintoma(credenciales_rechazadas, cuentas, 'El sistema rechaza el usuario o la contrasena').
sintoma(cuenta_bloqueada, cuentas, 'La cuenta fue bloqueada por intentos fallidos').
sintoma(no_imprime, impresoras, 'El documento no sale por la impresora').
sintoma(app_no_responde, apps_negocio, 'La aplicacion deja de responder').
sintoma(error_acceso_nube, nube, 'No se puede acceder a los archivos en la nube').

% ----------------------------------------------------------------
% 3. Contexto y evidencias del reporte
% contexto(Dato, ImpactoQueIndica, Descripcion): define el alcance.
% evidencia(Dato, Descripcion): informacion extra que permite
%                               descartar causas o detectar riesgos.
% ----------------------------------------------------------------
contexto(companeros_sin_internet, departamento, 'Otros usuarios del mismo departamento tampoco tienen Internet').
contexto(varios_usuarios_afectados, departamento, 'El mismo inconveniente afecta a varios usuarios del area').
contexto(toda_organizacion_afectada, organizacion, 'El inconveniente afecta a toda la organizacion').

evidencia(usa_wifi, 'El usuario se conecta por Wi-Fi').
evidencia(usa_cable, 'El usuario se conecta por cable de red').
evidencia(sospecha_seguridad, 'Hay indicios de acceso no autorizado, phishing o malware').

% ----------------------------------------------------------------
% 4. Causas probables
% causa(Causa, Descripcion).
% causa_sintoma(Causa, Sintoma): sintomas que puede explicar la causa.
% alcance_causa(Causa, Alcance): individual | colectivo | ambos.
% peso(Causa, Peso): frecuencia relativa (3 = muy comun, 1 = rara).
% ----------------------------------------------------------------
causa(cable_desconectado, 'El cable de red esta desconectado o danado').
causa(dhcp_sin_respuesta, 'El servidor DHCP no esta asignando direcciones IP').
causa(falla_infraestructura_red, 'Existe una falla en un equipo o enlace de red del departamento').
causa(punto_acceso_wifi, 'El punto de acceso inalambrico presenta una falla').
causa(vpn_gateway_caido, 'La puerta de enlace o concentrador VPN no esta disponible').
causa(correo_servidor_caido, 'El servidor de correo presenta una interrupcion').
causa(cuota_buzon_llena, 'El buzon alcanzo su limite de almacenamiento').
causa(controlador_impresora, 'El controlador de la impresora esta danado o desactualizado').
causa(cola_impresion_detenida, 'El servicio o la cola de impresion se encuentra detenida').
causa(contrasena_expirada, 'La contrasena de la cuenta ha expirado').
causa(intentos_fallidos, 'La cuenta se bloqueo por varios intentos de acceso incorrectos').
causa(certificado_vencido, 'El certificado digital utilizado por el servicio vencio').
causa(falta_recursos_equipo, 'El equipo tiene poca memoria o recursos disponibles').
causa(app_servicio_caido, 'El servicio de la aplicacion no esta disponible').
causa(sincronizacion_nube, 'La sincronizacion con el almacenamiento en la nube fallo').

causa_sintoma(cable_desconectado, sin_internet).
causa_sintoma(dhcp_sin_respuesta, sin_internet).
causa_sintoma(falla_infraestructura_red, sin_internet).
causa_sintoma(falla_infraestructura_red, vpn_caida).
causa_sintoma(falla_infraestructura_red, red_lenta).
causa_sintoma(punto_acceso_wifi, sin_internet).
causa_sintoma(punto_acceso_wifi, red_lenta).
causa_sintoma(vpn_gateway_caido, vpn_caida).
causa_sintoma(correo_servidor_caido, no_recibe_correos).
causa_sintoma(correo_servidor_caido, no_envia_correos).
causa_sintoma(cuota_buzon_llena, no_recibe_correos).
causa_sintoma(controlador_impresora, no_imprime).
causa_sintoma(cola_impresion_detenida, no_imprime).
causa_sintoma(contrasena_expirada, credenciales_rechazadas).
causa_sintoma(intentos_fallidos, credenciales_rechazadas).
causa_sintoma(intentos_fallidos, cuenta_bloqueada).
causa_sintoma(certificado_vencido, vpn_caida).
causa_sintoma(certificado_vencido, error_acceso_nube).
causa_sintoma(falta_recursos_equipo, equipo_lento).
causa_sintoma(falta_recursos_equipo, pantalla_azul).
causa_sintoma(app_servicio_caido, app_no_responde).
causa_sintoma(sincronizacion_nube, error_acceso_nube).

alcance_causa(cable_desconectado, individual).
alcance_causa(dhcp_sin_respuesta, ambos).
alcance_causa(falla_infraestructura_red, colectivo).
alcance_causa(punto_acceso_wifi, ambos).
alcance_causa(vpn_gateway_caido, colectivo).
alcance_causa(correo_servidor_caido, colectivo).
alcance_causa(cuota_buzon_llena, individual).
alcance_causa(controlador_impresora, individual).
alcance_causa(cola_impresion_detenida, ambos).
alcance_causa(contrasena_expirada, individual).
alcance_causa(intentos_fallidos, individual).
alcance_causa(certificado_vencido, ambos).
alcance_causa(falta_recursos_equipo, individual).
alcance_causa(app_servicio_caido, colectivo).
alcance_causa(sincronizacion_nube, individual).

peso(cable_desconectado, 3).
peso(dhcp_sin_respuesta, 2).
peso(falla_infraestructura_red, 2).
peso(punto_acceso_wifi, 2).
peso(vpn_gateway_caido, 2).
peso(correo_servidor_caido, 2).
peso(cuota_buzon_llena, 2).
peso(controlador_impresora, 1).
peso(cola_impresion_detenida, 3).
peso(contrasena_expirada, 3).
peso(intentos_fallidos, 3).
peso(certificado_vencido, 1).
peso(falta_recursos_equipo, 2).
peso(app_servicio_caido, 2).
peso(sincronizacion_nube, 2).

% Reglas de descarte: una evidencia contradice una causa que, por
% sus sintomas, si podria explicar el caso.
incompatibilidad(cable_desconectado, usa_wifi).
incompatibilidad(punto_acceso_wifi, usa_cable).

% ----------------------------------------------------------------
% 5. Pasos de solucion ordenados
% solucion(Causa, NumeroDePaso, Instruccion).
% ----------------------------------------------------------------
solucion(cable_desconectado, 1, 'Revisar que el cable este conectado al equipo y a la toma de red').
solucion(cable_desconectado, 2, 'Probar con otro cable de red que funcione').
solucion(cable_desconectado, 3, 'Verificar si el equipo recupera la conexion').

solucion(dhcp_sin_respuesta, 1, 'Comprobar si el equipo tiene una direccion IP valida').
solucion(dhcp_sin_respuesta, 2, 'Renovar la direccion IP desde la configuracion de red').
solucion(dhcp_sin_respuesta, 3, 'Si varios equipos siguen sin IP, revisar el servicio DHCP y escalar a redes').

solucion(falla_infraestructura_red, 1, 'Confirmar si otros usuarios del mismo departamento presentan la falla').
solucion(falla_infraestructura_red, 2, 'Registrar las areas y equipos afectados').
solucion(falla_infraestructura_red, 3, 'Revisar el estado de los equipos de red si se cuenta con permisos').
solucion(falla_infraestructura_red, 4, 'Escalar el caso al grupo de redes con la evidencia recopilada').

solucion(punto_acceso_wifi, 1, 'Verificar que el Wi-Fi este habilitado en el equipo').
solucion(punto_acceso_wifi, 2, 'Olvidar la red y conectarse nuevamente').
solucion(punto_acceso_wifi, 3, 'Comprobar si otros usuarios cercanos tienen el mismo problema').

solucion(vpn_gateway_caido, 1, 'Confirmar que el equipo tenga acceso a Internet').
solucion(vpn_gateway_caido, 2, 'Cerrar y abrir nuevamente el cliente VPN').
solucion(vpn_gateway_caido, 3, 'Registrar el mensaje de error y escalar al grupo de redes').

solucion(correo_servidor_caido, 1, 'Consultar si otros usuarios del departamento tampoco pueden utilizar el correo').
solucion(correo_servidor_caido, 2, 'Probar el acceso desde el correo web, si esta disponible').
solucion(correo_servidor_caido, 3, 'Escalar al grupo de infraestructura y correo').

solucion(cuota_buzon_llena, 1, 'Revisar el espacio disponible del buzon').
solucion(cuota_buzon_llena, 2, 'Eliminar o archivar mensajes que ya no se necesitan').
solucion(cuota_buzon_llena, 3, 'Solicitar ampliacion de cuota si el problema continua').

solucion(controlador_impresora, 1, 'Confirmar que la impresora correcta este seleccionada').
solucion(controlador_impresora, 2, 'Revisar el controlador instalado').
solucion(controlador_impresora, 3, 'Solicitar al soporte la reinstalacion del controlador si se requieren permisos').

solucion(cola_impresion_detenida, 1, 'Verificar que la impresora este encendida y conectada').
solucion(cola_impresion_detenida, 2, 'Cancelar los trabajos atascados en la cola').
solucion(cola_impresion_detenida, 3, 'Reiniciar el servicio de impresion si se cuenta con permisos').

solucion(contrasena_expirada, 1, 'Ingresar al portal institucional de cambio de contrasena').
solucion(contrasena_expirada, 2, 'Crear una contrasena nueva que cumpla las politicas establecidas').
solucion(contrasena_expirada, 3, 'Volver a iniciar sesion con la contrasena actualizada').

solucion(intentos_fallidos, 1, 'Confirmar la identidad del usuario mediante el procedimiento institucional').
solucion(intentos_fallidos, 2, 'Solicitar el desbloqueo de la cuenta por el canal autorizado').
solucion(intentos_fallidos, 3, 'Restablecer la contrasena si el usuario no la recuerda').
solucion(intentos_fallidos, 4, 'Comprobar el acceso y recomendar actualizar la contrasena guardada en otros dispositivos').

solucion(certificado_vencido, 1, 'Registrar el mensaje y la fecha de vencimiento del certificado').
solucion(certificado_vencido, 2, 'No instalar certificados por cuenta propia').
solucion(certificado_vencido, 3, 'Escalar al grupo de seguridad o infraestructura para renovar el certificado').

solucion(falta_recursos_equipo, 1, 'Guardar el trabajo y cerrar aplicaciones que no se esten utilizando').
solucion(falta_recursos_equipo, 2, 'Reiniciar el equipo cuando sea posible').
solucion(falta_recursos_equipo, 3, 'Si la lentitud o pantalla azul continua, escalar a soporte de equipos').

solucion(app_servicio_caido, 1, 'Cerrar la aplicacion y volver a abrirla').
solucion(app_servicio_caido, 2, 'Comprobar si otros usuarios pueden ingresar').
solucion(app_servicio_caido, 3, 'Registrar el mensaje de error y escalar al equipo de aplicaciones').

solucion(sincronizacion_nube, 1, 'Comprobar la conexion a Internet').
solucion(sincronizacion_nube, 2, 'Verificar que la sesion de la nube siga activa').
solucion(sincronizacion_nube, 3, 'Registrar el error de sincronizacion y escalar si persiste').

% ----------------------------------------------------------------
% 6. Matriz de prioridad, urgencia por servicio y SLA
% matriz_prioridad(Impacto, Urgencia, Prioridad).
% urgencia_componente(Componente, Urgencia): urgencia por defecto
%   segun lo critico que sea el servicio para la operacion.
% nivel_urgencia(Urgencia, Valor): permite comparar urgencias.
% sla(Prioridad, TiempoRespuesta, TiempoObjetivoResolucion).
% ----------------------------------------------------------------
matriz_prioridad(organizacion, alta, p1).
matriz_prioridad(organizacion, media, p1).
matriz_prioridad(organizacion, baja, p2).
matriz_prioridad(departamento, alta, p1).
matriz_prioridad(departamento, media, p2).
matriz_prioridad(departamento, baja, p3).
matriz_prioridad(individual, alta, p2).
matriz_prioridad(individual, media, p3).
matriz_prioridad(individual, baja, p4).

urgencia_componente(red, media).
urgencia_componente(correo, alta).
urgencia_componente(apps_negocio, alta).
urgencia_componente(vpn, media).
urgencia_componente(cuentas, media).
urgencia_componente(sistema_operativo, media).
urgencia_componente(nube, media).
urgencia_componente(impresoras, baja).

nivel_urgencia(baja, 1).
nivel_urgencia(media, 2).
nivel_urgencia(alta, 3).

sla(p1, '15 minutos', '4 horas').
sla(p2, '30 minutos', '8 horas').
sla(p3, '4 horas', '2 dias habiles').
sla(p4, '1 dia habil', '5 dias habiles').

% sla_horas(Prioridad, HorasRespuesta, HorasResolucion).
% Los mismos tiempos de sla/3 expresados en horas habiles, con una
% jornada laboral de 8 horas. La aplicacion los usa para calcular
% el porcentaje de cumplimiento del SLA.
sla_horas(p1, 0.25, 4).
sla_horas(p2, 0.5, 8).
sla_horas(p3, 4, 16).
sla_horas(p4, 8, 40).

% ----------------------------------------------------------------
% 7. Tipos de registro y peticiones de servicio
% peticion(Peticion, GrupoQueAtiende, Descripcion): solicitudes
%   estandar que no son fallos, por lo que se registran como
%   solicitud de servicio y no como incidente.
% ----------------------------------------------------------------
tipo_registro(incidente, 'Interrupcion o reduccion no planificada de un servicio').
tipo_registro(solicitud_servicio, 'Peticion de acceso, informacion, instalacion o servicio estandar').
tipo_registro(problema, 'Causa real o potencial de uno o varios incidentes, especialmente recurrentes').

peticion(instalar_software, mesa_ayuda, 'Instalacion de un programa autorizado').
peticion(nuevo_acceso, cuentas_y_accesos, 'Acceso a un sistema o carpeta compartida').
peticion(ampliar_cuota_buzon, infraestructura, 'Aumento del espacio del buzon de correo').

% ----------------------------------------------------------------
% 8. Grupos resolutores y condiciones de escalamiento
% grupo_resolutor(Grupo, Nivel, Descripcion).
% requiere_grupo(Causa, Grupo): grupo especialista que atiende la
%   causa SI el caso debe escalarse.
% requiere_permisos_admin(Causa): la solucion no puede aplicarla la
%   mesa de ayuda porque necesita permisos administrativos.
% grupo_por_componente(Componente, Grupo): se usa cuando no se
%   encuentra ninguna causa registrada.
% ----------------------------------------------------------------
grupo_resolutor(mesa_ayuda, primer_nivel, 'Atencion inicial, verificaciones y soluciones conocidas').
grupo_resolutor(redes, segundo_nivel, 'Conectividad, DHCP, Wi-Fi, enlaces y VPN').
grupo_resolutor(cuentas_y_accesos, segundo_nivel, 'Desbloqueos y administracion de cuentas').
grupo_resolutor(soporte_equipos, segundo_nivel, 'Sistema operativo, hardware y controladores').
grupo_resolutor(aplicaciones, segundo_nivel, 'Aplicaciones institucionales y servicios de negocio').
grupo_resolutor(infraestructura, segundo_nivel, 'Servidores, correo y servicios centrales').
grupo_resolutor(ciberseguridad, tercer_nivel, 'Certificados, accesos sospechosos e incidentes de seguridad').

requiere_grupo(cable_desconectado, redes).
requiere_grupo(dhcp_sin_respuesta, redes).
requiere_grupo(falla_infraestructura_red, redes).
requiere_grupo(punto_acceso_wifi, redes).
requiere_grupo(vpn_gateway_caido, redes).
requiere_grupo(correo_servidor_caido, infraestructura).
requiere_grupo(cuota_buzon_llena, infraestructura).
requiere_grupo(controlador_impresora, soporte_equipos).
requiere_grupo(cola_impresion_detenida, soporte_equipos).
requiere_grupo(contrasena_expirada, cuentas_y_accesos).
requiere_grupo(intentos_fallidos, cuentas_y_accesos).
requiere_grupo(certificado_vencido, ciberseguridad).
requiere_grupo(falta_recursos_equipo, soporte_equipos).
requiere_grupo(app_servicio_caido, aplicaciones).
requiere_grupo(sincronizacion_nube, infraestructura).

requiere_permisos_admin(dhcp_sin_respuesta).
requiere_permisos_admin(falla_infraestructura_red).
requiere_permisos_admin(vpn_gateway_caido).
requiere_permisos_admin(correo_servidor_caido).
requiere_permisos_admin(controlador_impresora).
requiere_permisos_admin(app_servicio_caido).

grupo_por_componente(red, redes).
grupo_por_componente(vpn, redes).
grupo_por_componente(correo, infraestructura).
grupo_por_componente(nube, infraestructura).
grupo_por_componente(sistema_operativo, soporte_equipos).
grupo_por_componente(impresoras, soporte_equipos).
grupo_por_componente(cuentas, cuentas_y_accesos).
grupo_por_componente(apps_negocio, aplicaciones).

% ----------------------------------------------------------------
% 9. Incidentes abiertos para correlacion
% incidente_previo(ID, Componente, Sintoma, Departamento, Estado).
% Es dinamico: la aplicacion carga aqui los tiquetes abiertos de la
% base de datos antes de cada diagnostico y los retira al terminar.
% Los incidentes de ejemplo para pruebas estan en datos_ejemplo.pl.
% ----------------------------------------------------------------
:- dynamic incidente_previo/5.
