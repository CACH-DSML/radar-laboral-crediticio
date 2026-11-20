"""Métricas de validación de un modelo de probabilidad.

Cada función recibe el evento observado (0 o 1) y la probabilidad estimada.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def auc(y: np.ndarray, p: np.ndarray) -> float:
    """Probabilidad de que un caso con evento reciba más puntaje que uno sin evento."""
    return float(roc_auc_score(y, p))


def ks(y: np.ndarray, p: np.ndarray) -> float:
    """Kolmogorov-Smirnov: la mayor distancia entre las distribuciones acumuladas del
    puntaje de quienes tuvieron el evento y de quienes no. Va de 0 a 1."""
    orden = np.argsort(p, kind="stable")
    y = np.asarray(y, dtype=float)[orden]
    p = np.asarray(p, dtype=float)[orden]
    con = np.cumsum(y) / y.sum()
    sin = np.cumsum(1 - y) / (1 - y).sum()
    # Con puntajes empatados solo cuenta la distancia al terminar cada grupo de empates.
    fin_de_empate = np.append(p[1:] != p[:-1], True)
    return float(np.abs(con - sin)[fin_de_empate].max())


def brier(y: np.ndarray, p: np.ndarray) -> float:
    """Error cuadrático medio de la probabilidad. Menor es mejor."""
    return float(np.mean((np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2))


def tabla_calibracion(y: np.ndarray, p: np.ndarray, grupos: int = 10) -> pd.DataFrame:
    """Compara, por tramos de puntaje de igual tamaño, lo estimado con lo observado.

    Un modelo bien calibrado tiene `estimado` cerca de `observado` en cada tramo.
    """
    tabla = pd.DataFrame({"y": np.asarray(y, dtype=float), "p": np.asarray(p, dtype=float)})
    tabla["tramo"] = pd.qcut(tabla["p"].rank(method="first"), grupos, labels=False) + 1
    resumen = tabla.groupby("tramo").agg(
        n=("y", "size"), estimado=("p", "mean"), observado=("y", "mean")
    )
    return resumen.reset_index()


def error_de_calibracion(y: np.ndarray, p: np.ndarray, grupos: int = 10) -> float:
    """Promedio, ponderado por tamaño, de la distancia entre estimado y observado."""
    tabla = tabla_calibracion(y, p, grupos)
    return float(
        (tabla["n"] * (tabla["estimado"] - tabla["observado"]).abs()).sum() / tabla["n"].sum()
    )


def psi(referencia: np.ndarray, actual: np.ndarray, grupos: int = 10) -> float:
    """Índice de estabilidad poblacional entre dos distribuciones de puntaje.

    Los tramos se fijan con los deciles de la referencia. Regla usual: menos de 0,10 es
    estable; entre 0,10 y 0,25 hay un cambio que conviene mirar; más de 0,25 es un cambio
    grande.
    """
    referencia = np.asarray(referencia, dtype=float)
    actual = np.asarray(actual, dtype=float)
    cortes = np.unique(np.quantile(referencia, np.linspace(0, 1, grupos + 1)[1:-1]))
    en_referencia = np.bincount(np.searchsorted(cortes, referencia), minlength=len(cortes) + 1)
    en_actual = np.bincount(np.searchsorted(cortes, actual), minlength=len(cortes) + 1)
    a = np.clip(en_referencia / en_referencia.sum(), 1e-6, None)
    b = np.clip(en_actual / en_actual.sum(), 1e-6, None)
    return float(((b - a) * np.log(b / a)).sum())


def resumen(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {
        "n": float(len(y)),
        "tasa_observada": float(np.mean(y)),
        "auc": auc(y, p),
        "ks": ks(y, p),
        "brier": brier(y, p),
        "error_calibracion": error_de_calibracion(y, p),
    }
