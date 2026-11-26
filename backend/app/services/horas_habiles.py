"""Calculo de horas habiles entre dos fechas, para medir el SLA.

El motor Prolog define el SLA en horas habiles (por ejemplo, P3 = 2 dias
habiles = 16 h con una jornada de 8 h). Aqui se cuentan solo las horas
dentro de la jornada laboral, de lunes a viernes, en hora local.
No se descuentan feriados.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from app.config import Configuracion


@dataclass(frozen=True)
class Jornada:
    inicio: time
    fin: time
    zona: timezone

    @classmethod
    def desde_config(cls, config: Configuracion) -> "Jornada":
        return cls(time(config.jornada_inicio_hora), time(config.jornada_fin_hora),
                   timezone(timedelta(hours=config.zona_horaria_utc_offset)))


def horas_habiles(inicio: datetime, fin: datetime, jornada: Jornada) -> float:
    """Horas habiles entre inicio y fin (ambas fechas con zona horaria)."""
    if fin <= inicio:
        return 0.0
    desde, hasta = inicio.astimezone(jornada.zona), fin.astimezone(jornada.zona)
    total = timedelta()
    dia = desde.date()
    while dia <= hasta.date():
        if dia.weekday() < 5:  # lunes (0) a viernes (4)
            apertura = datetime.combine(dia, jornada.inicio, jornada.zona)
            cierre = datetime.combine(dia, jornada.fin, jornada.zona)
            tramo_inicio, tramo_fin = max(apertura, desde), min(cierre, hasta)
            if tramo_fin > tramo_inicio:
                total += tramo_fin - tramo_inicio
        dia += timedelta(days=1)
    return round(total.total_seconds() / 3600, 2)
