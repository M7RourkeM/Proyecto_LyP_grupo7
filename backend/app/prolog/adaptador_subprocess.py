"""Adaptador que ejecuta SWI-Prolog como proceso externo (swipl -g ... -t halt).

Cada consulta arranca un proceso nuevo: es mas lento que pyswip, pero
aislado (un error o un ciclo infinito en Prolog no afecta a la API) y no
depende de la version de la biblioteca nativa de SWI-Prolog.
"""

import subprocess

from app.prolog.adaptador_base import (RUTA_PUENTE, AdaptadorProlog, ErrorProlog,
                                       PrologNoDisponible, PrologTimeout)

# Las rutas llegan como los dos ultimos argumentos (despues de --), no
# dentro del codigo Prolog, asi no hay que escapar espacios ni comillas.
# halt(0) va fuera del catch: en SWI-Prolog 9.3+ halt/1 lanza una excepcion.
OBJETIVO = (
    "current_prolog_flag(argv, A), append(_, [Kb, Puente], A),"
    "load_files(Kb, [silent(true)]), load_files(Puente, [silent(true)]),"
    "catch(puente_main, E, (print_message(error, E), halt(2))),"
    "halt(0)"
)

# Margen sobre el limite interno de Prolog para el arranque del proceso.
MARGEN_ARRANQUE_S = 10


class AdaptadorSubprocess(AdaptadorProlog):
    nombre = "subprocess"

    def _ejecutar(self, texto_entrada: str) -> str:
        comando = [self.config.swipl_ejecutable, "-q", "-g", OBJETIVO, "-t", "halt(1)",
                   "--", str(self.ruta_kb), str(RUTA_PUENTE)]
        try:
            resultado = subprocess.run(
                comando, input=texto_entrada, capture_output=True, text=True,
                encoding="utf-8", cwd=self.ruta_kb.parent,
                timeout=self.config.prolog_timeout_s + MARGEN_ARRANQUE_S,
            )
        except FileNotFoundError as error:
            raise PrologNoDisponible(
                f"No se encontro el ejecutable de Prolog: {self.config.swipl_ejecutable}") from error
        except subprocess.TimeoutExpired as error:
            raise PrologTimeout("El proceso de Prolog excedio el tiempo limite") from error
        if resultado.returncode != 0 or not resultado.stdout.strip():
            raise ErrorProlog(f"Prolog termino con codigo {resultado.returncode}: "
                              f"{resultado.stderr.strip()[:500]}")
        return resultado.stdout
