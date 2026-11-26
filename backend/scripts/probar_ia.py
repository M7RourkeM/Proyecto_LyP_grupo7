"""Genera con Ollama la guia y la nota de un escenario, y muestra todo el proceso.

No usa la base de datos: consulta al motor Prolog, arma el contexto y llama a
la IA real, igual que al crear un tiquete.

Uso (desde la carpeta backend, con Ollama corriendo):
    .venv\\Scripts\\python -m scripts.probar_ia
    .venv\\Scripts\\python -m scripts.probar_ia --escenario correo
"""

import argparse
import time

from app.config import obtener_configuracion
from app.ia.cliente_ollama import ClienteOllama
from app.ia.generador import generar_textos
from app.prolog.fabrica import crear_adaptador
from app.schemas.prolog import EntradaDiagnostico

ESCENARIOS = {
    "red": EntradaDiagnostico(servicio="red", componente="red_cableada",
                              sintomas=["sin_internet", "vpn_caida"], alcance="individual",
                              urgencia="media", departamento="ventas"),
    "correo": EntradaDiagnostico(servicio="correo", sintomas=["no_recibe_correos"],
                                 alcance="departamento", urgencia="alta",
                                 departamento="finanzas"),
    "cuenta": EntradaDiagnostico(servicio="cuentas", sintomas=["cuenta_bloqueada"],
                                 alcance="individual", urgencia="media", departamento="ventas"),
    "impresora": EntradaDiagnostico(servicio="impresoras", sintomas=["no_imprime"],
                                    alcance="individual", urgencia="baja",
                                    departamento="operaciones"),
}


def seccion(titulo: str, texto: str) -> None:
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}\n{texto}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba la IA con un escenario real.")
    parser.add_argument("--escenario", choices=ESCENARIOS, default="red")
    args = parser.parse_args()

    config = obtener_configuracion()
    adaptador = crear_adaptador(config)
    entrada = ESCENARIOS[args.escenario]
    diagnostico = adaptador.diagnosticar(entrada)
    catalogo = adaptador.catalogo()
    descripciones = {i.codigo: i.descripcion for i in catalogo.sintomas}

    contexto = diagnostico.model_dump(exclude={"incidentes_relacionados"})
    contexto["departamento"] = entrada.departamento
    contexto["sintomas"] = [descripciones.get(s, s) for s in entrada.sintomas]

    inicio = time.perf_counter()
    resultado = generar_textos(contexto, ClienteOllama(config))
    segundos = time.perf_counter() - inicio

    seccion("PROMPT ENVIADO A LA IA", resultado.prompt)
    seccion("GUIA PARA EL USUARIO", resultado.guia_usuario)
    seccion("NOTA TECNICA PARA EL AGENTE", resultado.nota_tecnica)
    seccion("RESULTADO", f"{resultado.resultado} (modelo {config.ollama_modelo}, "
                         f"{segundos:.1f} s)\nErrores del validador: "
                         f"{resultado.errores or 'ninguno'}")


if __name__ == "__main__":
    main()
