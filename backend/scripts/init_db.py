"""Crea las tablas de la base de datos.

Uso (desde la carpeta backend):
    .venv\\Scripts\\python -m scripts.init_db              crea las tablas que falten
    .venv\\Scripts\\python -m scripts.init_db --reiniciar  borra todo y crea de nuevo
"""

import argparse

from sqlalchemy import Engine

import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.database import Base, motor


def crear_tablas(motor_bd: Engine, reiniciar: bool = False) -> None:
    if reiniciar:
        Base.metadata.drop_all(motor_bd)
    Base.metadata.create_all(motor_bd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea las tablas de la base de datos.")
    parser.add_argument("--reiniciar", action="store_true",
                        help="borra todas las tablas antes de crearlas")
    args = parser.parse_args()
    crear_tablas(motor, reiniciar=args.reiniciar)
    print(f"Tablas creadas en {motor.url}: {', '.join(sorted(Base.metadata.tables))}")


if __name__ == "__main__":
    main()
