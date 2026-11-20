"""Regla para decidir si una celda se publica.

Los umbrales los decide el autor y están en `parametros.py`. Aquí no hay valores por
defecto a propósito.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from radar.indicadores.estimacion import Estimacion

Calidad = Literal["publicable", "referencial", "suprimida"]


@dataclass(frozen=True)
class ReglaSupresion:
    """Umbrales de la regla.

    n_minimo:        filas mínimas del dominio para publicar.
    upm_minimas:     conglomerados mínimos con filas del dominio.
    cv_referencial:  desde este coeficiente de variación la celda es solo referencial.
    cv_maximo:       desde este coeficiente de variación la celda se suprime.
    """

    n_minimo: int
    upm_minimas: int
    cv_referencial: float
    cv_maximo: float


def clasificar(estimacion: Estimacion, regla: ReglaSupresion) -> Calidad:
    """Clasifica una celda. Una celda sin error estándar se juzga solo por su muestra.

    Primero la muestra: con pocos casos o pocos conglomerados, el propio error estándar
    es poco confiable, así que la celda se suprime sin mirarlo. Después la precisión.
    """
    if estimacion.n < regla.n_minimo or estimacion.n_upm < regla.upm_minimas:
        return "suprimida"
    if math.isnan(estimacion.cv):
        return "publicable"
    if estimacion.cv >= regla.cv_maximo:
        return "suprimida"
    if estimacion.cv >= regla.cv_referencial:
        return "referencial"
    return "publicable"
