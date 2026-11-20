"""Pronosticadores a un paso y su evaluación fuera de muestra.

Los tests que definen qué debe devolver cada función están en `tests/test_nowcast.py`.

Un pronosticador es una función que recibe dos cosas y devuelve un número:

- `entrenamiento`: las filas anteriores al trimestre que se quiere estimar, en orden.
- `fila_nueva`: la fila de ese trimestre. Trae los indicadores de alta frecuencia, que
  ya se conocen, pero **no** el valor del objetivo, que es justamente lo que falta.

Las tres funciones de abajo construyen pronosticadores. `evaluar_origen_movil` los
prueba de la única forma honesta con una serie corta: avanzando en el tiempo y usando
en cada paso solo lo que se sabía hasta entonces.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd

Pronosticador = Callable[[pd.DataFrame, pd.Series], float]


def ingenuo(objetivo: str) -> Pronosticador:
    """Baseline: el pronóstico es el último valor observado del objetivo."""

    def pronosticar(entrenamiento: pd.DataFrame, fila_nueva: pd.Series) -> float:
        return float(entrenamiento[objetivo].iloc[-1])

    return pronosticar


def ingenuo_estacional(objetivo: str, periodos: int = 4) -> Pronosticador:
    """Baseline estacional: mismo trimestre del año anterior más la última variación anual.

    Con `y` el objetivo, `t` el último trimestre observado y `p = periodos`:
    pronóstico = y[t + 1 − p] + (y[t] − y[t − p]).
    Necesita al menos `p + 1` observaciones; con menos, `ValueError`.
    """

    def pronosticar(entrenamiento: pd.DataFrame, fila_nueva: pd.Series) -> float:
        y = entrenamiento[objetivo].to_numpy(dtype=float)
        if len(y) < periodos + 1:
            raise ValueError(
                f"El baseline estacional necesita {periodos + 1} observaciones y hay {len(y)}"
            )
        mismo_trimestre_del_anio_anterior = y[-periodos]
        ultima_variacion_anual = y[-1] - y[-1 - periodos]
        return float(mismo_trimestre_del_anio_anterior + ultima_variacion_anual)

    return pronosticar


def puente(objetivo: str, regresores: list[str]) -> Pronosticador:
    """Ecuación puente: mínimos cuadrados del objetivo sobre los regresores, con intercepto.

    Se estima con `entrenamiento` y se evalúa en los regresores de `fila_nueva`. Con
    menos observaciones que parámetros, `ValueError`.
    """

    def pronosticar(entrenamiento: pd.DataFrame, fila_nueva: pd.Series) -> float:
        parametros = len(regresores) + 1
        if len(entrenamiento) < parametros:
            raise ValueError(
                f"La ecuación puente tiene {parametros} parámetros y solo hay "
                f"{len(entrenamiento)} observaciones"
            )
        x = entrenamiento[regresores].to_numpy(dtype=float)
        matriz = np.column_stack([np.ones(len(x)), x])
        coeficientes, *_ = np.linalg.lstsq(
            matriz, entrenamiento[objetivo].to_numpy(dtype=float), rcond=None
        )
        nuevos = fila_nueva[regresores].to_numpy(dtype=float)
        return float(coeficientes[0] + nuevos @ coeficientes[1:])

    return pronosticar


def evaluar_origen_movil(
    datos: pd.DataFrame, objetivo: str, pronosticador: Pronosticador, inicio: int
) -> pd.DataFrame:
    """Evalúa un pronosticador avanzando un trimestre a la vez.

    Para cada posición `t` desde `inicio` hasta el final: entrena con las `t` primeras
    filas y pronostica la fila `t`, a la que antes le borra el valor del objetivo.

    Devuelve una tabla con el índice de las filas pronosticadas y las columnas `real`,
    `pronostico` y `error` (pronóstico menos real).
    """
    if not 1 <= inicio < len(datos):
        raise ValueError(
            f"El inicio debe estar entre 1 y {len(datos) - 1}; se recibió inicio={inicio}"
        )
    filas = []
    for t in range(inicio, len(datos)):
        fila_nueva = datos.iloc[t].copy()
        real = float(fila_nueva[objetivo])
        fila_nueva[objetivo] = math.nan  # lo que se quiere estimar no se puede ver
        pronostico = pronosticador(datos.iloc[:t].copy(), fila_nueva)
        filas.append({"real": real, "pronostico": pronostico, "error": pronostico - real})
    return pd.DataFrame(filas, index=datos.index[inicio:])


def error_absoluto_medio(evaluacion: pd.DataFrame) -> float:
    """Promedio del valor absoluto de la columna `error`."""
    return float(evaluacion["error"].abs().mean())
