"""Ejecuta una consulta SQL de solo lectura contra la base de datos y muestra el resultado.

Uso (desde la carpeta backend):
    .venv\\Scripts\\python -m scripts.consulta_sql
    .venv\\Scripts\\python -m scripts.consulta_sql "SELECT codigo, nivel FROM grupo_resolutor"
"""

import sys

from sqlalchemy import text

from app.database import motor

CONSULTA_POR_DEFECTO = """
SELECT d.nombre AS departamento,
       COUNT(DISTINCT u.id) AS usuarios,
       COUNT(DISTINCT a.id) AS activos
FROM departamento d
LEFT JOIN usuario u ON u.departamento_id = d.id
LEFT JOIN activo  a ON a.departamento_id = d.id
GROUP BY d.id
ORDER BY d.nombre
"""


def mostrar(consulta: str) -> None:
    if not consulta.lstrip().upper().startswith("SELECT"):
        sys.exit("Solo se permiten consultas SELECT.")
    with motor.connect() as conexion:
        resultado = conexion.execute(text(consulta))
        columnas = list(resultado.keys())
        filas = [[str(valor) for valor in fila] for fila in resultado]
    anchos = [max(len(c), *(len(f[i]) for f in filas)) if filas else len(c)
              for i, c in enumerate(columnas)]
    print(consulta.strip(), end="\n\n")
    print("  ".join(c.ljust(a) for c, a in zip(columnas, anchos)))
    print("  ".join("-" * a for a in anchos))
    for fila in filas:
        print("  ".join(v.ljust(a) for v, a in zip(fila, anchos)))
    print(f"\n({len(filas)} filas)")


if __name__ == "__main__":
    mostrar(sys.argv[1] if len(sys.argv) > 1 else CONSULTA_POR_DEFECTO)
