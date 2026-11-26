"""Carga datos de prueba: 5 departamentos, 7 grupos, 10 usuarios, 4 agentes y 15 activos.

Todos los datos personales son ficticios. Los correos usan el dominio
reservado .test, que no existe en Internet.

Uso (desde la carpeta backend; reinicia la base antes de cargar):
    .venv\\Scripts\\python -m scripts.seed
"""

from sqlalchemy.orm import Session

from app.database import SesionLocal, motor
from app.models import Activo, Agente, Departamento, GrupoResolutor, Usuario
from scripts.init_db import crear_tablas

DOMINIO = "empresa-demo.test"

# Codigos identicos a los atomos del motor Prolog.
DEPARTAMENTOS = [
    ("finanzas", "Finanzas"),
    ("ventas", "Ventas"),
    ("recursos_humanos", "Recursos Humanos"),
    ("tecnologia", "Tecnologia"),
    ("operaciones", "Operaciones"),
]

# Coinciden con grupo_resolutor/3 de base_conocimiento.pl (lo verifica un test).
GRUPOS = [
    ("mesa_ayuda", "Mesa de ayuda", 1, "Atencion inicial, verificaciones y soluciones conocidas"),
    ("redes", "Redes", 2, "Conectividad, DHCP, Wi-Fi, enlaces y VPN"),
    ("cuentas_y_accesos", "Cuentas y accesos", 2, "Desbloqueos y administracion de cuentas"),
    ("soporte_equipos", "Soporte de equipos", 2, "Sistema operativo, hardware y controladores"),
    ("aplicaciones", "Aplicaciones", 2, "Aplicaciones institucionales y servicios de negocio"),
    ("infraestructura", "Infraestructura", 2, "Servidores, correo y servicios centrales"),
    ("ciberseguridad", "Ciberseguridad", 3, "Certificados, accesos sospechosos e incidentes de seguridad"),
]

# (nombre, usuario del correo, telefono, identificacion, departamento)
USUARIOS = [
    ("Laura Mendez Solis", "lmendez", "8800-0001", "1-1111-0001", "finanzas"),
    ("Carlos Jimenez Rojas", "cjimenez", "8800-0002", "1-1111-0002", "finanzas"),
    ("Andrea Vargas Mora", "avargas", "8800-0003", "1-1111-0003", "ventas"),
    ("Diego Castro Alfaro", "dcastro", "8800-0004", "1-1111-0004", "ventas"),
    ("Sofia Araya Quesada", "saraya", "8800-0005", "1-1111-0005", "recursos_humanos"),
    ("Jose Pablo Brenes Vega", "jbrenes", "8800-0006", "1-1111-0006", "recursos_humanos"),
    ("Mariana Chaves Ulate", "mchaves", "8800-0007", "1-1111-0007", "tecnologia"),
    ("Andres Salas Campos", "asalas", "8800-0008", "1-1111-0008", "tecnologia"),
    ("Valeria Herrera Nunez", "vherrera", "8800-0009", "1-1111-0009", "operaciones"),
    ("Esteban Rojas Fallas", "erojas", "8800-0010", "1-1111-0010", "operaciones"),
]

# (nombre, usuario del correo, grupo)
AGENTES = [
    ("Daniela Soto Arias", "dsoto.soporte", "mesa_ayuda"),
    ("Ricardo Monge Leon", "rmonge.soporte", "mesa_ayuda"),
    ("Natalia Cordero Pineda", "ncordero.redes", "redes"),
    ("Fernando Urena Calvo", "furena.infra", "infraestructura"),
]

# (codigo, tipo, marca y modelo, sistema operativo, ubicacion, departamento, usuario o None)
ACTIVOS = [
    ("LAP-001", "laptop", "Dell Latitude 5440", "Windows 11", "Edificio A, piso 2", "finanzas", "lmendez"),
    ("LAP-002", "laptop", "Dell Latitude 5440", "Windows 11", "Edificio A, piso 2", "finanzas", "cjimenez"),
    ("LAP-003", "laptop", "Lenovo ThinkPad E14", "Windows 11", "Edificio B, piso 1", "ventas", "avargas"),
    ("LAP-004", "laptop", "Lenovo ThinkPad E14", "Windows 10", "Edificio B, piso 1", "ventas", "dcastro"),
    ("LAP-005", "laptop", "HP ProBook 450", "Windows 11", "Edificio A, piso 3", "recursos_humanos", "saraya"),
    ("LAP-006", "laptop", "HP ProBook 450", "Windows 11", "Edificio A, piso 3", "recursos_humanos", "jbrenes"),
    ("LAP-007", "laptop", "Lenovo ThinkPad T14", "Ubuntu 24.04", "Edificio C, piso 1", "tecnologia", "mchaves"),
    ("LAP-008", "laptop", "Lenovo ThinkPad T14", "Windows 11", "Edificio C, piso 1", "tecnologia", "asalas"),
    ("LAP-009", "laptop", "Dell Latitude 3540", "Windows 11", "Bodega central", "operaciones", "vherrera"),
    ("ESC-001", "escritorio", "HP EliteDesk 800", "Windows 10", "Bodega central", "operaciones", "erojas"),
    ("IMP-001", "impresora", "HP LaserJet M507", None, "Edificio A, piso 2", "finanzas", None),
    ("IMP-002", "impresora", "Brother HL-L6200", None, "Edificio B, piso 1", "ventas", None),
    ("TEL-001", "telefono", "Samsung Galaxy A55", "Android 15", "Edificio B, piso 1", "ventas", "avargas"),
    ("SRV-001", "servidor", "Dell PowerEdge R650", "Windows Server 2022", "Centro de datos", "tecnologia", None),
    ("SRV-002", "servidor", "Dell PowerEdge R450", "Ubuntu Server 24.04", "Centro de datos", "tecnologia", None),
]


def cargar_datos(sesion: Session) -> None:
    """Inserta los datos de prueba en una base vacia."""
    deptos = {codigo: Departamento(codigo=codigo, nombre=nombre) for codigo, nombre in DEPARTAMENTOS}
    grupos = {codigo: GrupoResolutor(codigo=codigo, nombre=nombre, nivel=nivel, descripcion=desc)
              for codigo, nombre, nivel, desc in GRUPOS}
    usuarios = {
        alias: Usuario(nombre=nombre, correo=f"{alias}@{DOMINIO}", telefono=tel,
                       identificacion=ced, departamento=deptos[depto])
        for nombre, alias, tel, ced, depto in USUARIOS
    }
    agentes = [Agente(nombre=nombre, correo=f"{alias}@{DOMINIO}", grupo=grupos[grupo])
               for nombre, alias, grupo in AGENTES]
    activos = [
        Activo(codigo_inventario=codigo, tipo=tipo, marca_modelo=modelo, sistema_operativo=so,
               ubicacion=ubic, departamento=deptos[depto],
               usuario=usuarios[alias] if alias else None)
        for codigo, tipo, modelo, so, ubic, depto, alias in ACTIVOS
    ]
    sesion.add_all([*deptos.values(), *grupos.values(), *usuarios.values(), *agentes, *activos])
    sesion.commit()


def main() -> None:
    crear_tablas(motor, reiniciar=True)
    with SesionLocal() as sesion:
        cargar_datos(sesion)
        print("Datos cargados: "
              f"{len(DEPARTAMENTOS)} departamentos, {len(GRUPOS)} grupos, "
              f"{len(USUARIOS)} usuarios, {len(AGENTES)} agentes, {len(ACTIVOS)} activos.")


if __name__ == "__main__":
    main()
