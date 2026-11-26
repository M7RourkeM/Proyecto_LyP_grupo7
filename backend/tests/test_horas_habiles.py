"""Calculo de horas habiles. Cada caso esta verificado a mano en el comentario.

Jornada: lunes a viernes de 8:00 a 16:00, hora de Costa Rica (UTC-6).
El 26 de noviembre de 2026 es jueves.
"""

from datetime import datetime, time, timedelta, timezone

import pytest

from app.services.horas_habiles import Jornada, horas_habiles

CR = timezone(timedelta(hours=-6))
JORNADA = Jornada(time(8), time(16), CR)


def cr(dia, hora, minuto=0) -> datetime:
    return datetime(2026, 11, dia, hora, minuto, tzinfo=CR)


@pytest.mark.parametrize("inicio,fin,esperado,explicacion", [
    (cr(26, 9), cr(26, 12), 3.0,
     "jueves 9:00 a 12:00 = 3 h"),
    (cr(26, 15), cr(27, 10), 3.0,
     "jueves 15:00-16:00 (1 h) + viernes 8:00-10:00 (2 h) = 3 h"),
    (cr(27, 14), cr(30, 9), 3.0,
     "viernes 14:00-16:00 (2 h) + sabado y domingo (0) + lunes 8:00-9:00 (1 h) = 3 h"),
    (cr(30, 6), cr(30, 9), 1.0,
     "lunes 6:00 (antes de abrir) a 9:00 = solo 8:00-9:00 = 1 h"),
    (cr(26, 17), cr(27, 7), 0.0,
     "jueves 17:00 a viernes 7:00: todo fuera de jornada = 0 h"),
    (cr(28, 10), cr(29, 15), 0.0,
     "sabado a domingo = 0 h"),
    (cr(26, 8), cr(27, 16), 16.0,
     "jueves y viernes completos = 8 + 8 = 16 h (el SLA de una P3)"),
    (cr(26, 9, 30), cr(26, 9, 45), 0.25,
     "15 minutos = 0,25 h (el tiempo de respuesta de una P1)"),
])
def test_horas_habiles_calculadas_a_mano(inicio, fin, esperado, explicacion):
    assert horas_habiles(inicio, fin, JORNADA) == esperado, explicacion


def test_las_fechas_en_utc_se_convierten_a_hora_de_costa_rica():
    # 15:00 UTC = 9:00 en Costa Rica; 18:00 UTC = 12:00 en Costa Rica -> 3 h
    inicio = datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)
    fin = datetime(2026, 11, 26, 18, 0, tzinfo=timezone.utc)
    assert horas_habiles(inicio, fin, JORNADA) == 3.0


def test_fin_anterior_al_inicio_da_cero():
    assert horas_habiles(cr(27, 10), cr(26, 10), JORNADA) == 0.0
