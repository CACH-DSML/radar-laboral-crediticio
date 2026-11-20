"""Herramientas de validación al estilo de un equipo de riesgos.

Complementan `metricas.py` con lo que pide un documento de validación de un modelo de
riesgo: Weight of Evidence e Information Value por variable, tabla de deciles con
captura y lift, curva KS y estabilidad por variable (CSI).

Convención de signos: el "evento" es lo malo (perder ingreso). El WoE de un tramo es
ln(% de no eventos / % de eventos), así que un WoE negativo marca un tramo más riesgoso
que el promedio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SIN_DATO = "(sin dato)"
# Una variable numérica con pocos valores distintos se trata como categórica.
MAXIMO_VALORES_DISCRETOS = 10


def _es_continua(valores: pd.Series) -> bool:
    return (
        pd.api.types.is_numeric_dtype(valores)
        and valores.nunique(dropna=True) > MAXIMO_VALORES_DISCRETOS
    )


def cortes_por_cuantil(referencia: pd.Series, grupos: int = 10) -> np.ndarray:
    """Cortes interiores de los cuantiles de la referencia, sin repetidos."""
    limpios = referencia.dropna().astype(float)
    return np.unique(np.quantile(limpios, np.linspace(0, 1, grupos + 1)[1:-1]))


def asignar_tramos(valores: pd.Series, cortes: np.ndarray | None) -> pd.Series:
    """Etiqueta de tramo para cada valor.

    Con `cortes`, la variable es continua y cada tramo es un intervalo `(a, b]`. Sin
    cortes, cada valor es su propio tramo. Los faltantes van a su propio tramo.
    """
    if cortes is None:
        return valores.astype("string").fillna(SIN_DATO).astype(object)
    bordes = np.concatenate([[-np.inf], cortes, [np.inf]])
    etiquetas = [f"({_fmt(bordes[i])}, {_fmt(bordes[i + 1])}]" for i in range(len(bordes) - 1)]
    tramos = pd.cut(valores.astype(float), bordes, labels=etiquetas, right=True)
    return tramos.astype(object).where(valores.notna(), SIN_DATO)


def _fmt(numero: float) -> str:
    if np.isinf(numero):
        return "-inf" if numero < 0 else "inf"
    return f"{numero:.3g}"


def tabla_woe(
    valores: pd.Series, y: np.ndarray, grupos: int = 10, suavizado: float = 0.5
) -> pd.DataFrame:
    """Tasa del evento, WoE y aporte al IV de cada tramo de una variable.

    Las variables continuas se cortan en `grupos` tramos por cuantiles; las demás usan
    sus valores. `suavizado` se suma a los conteos para que un tramo sin eventos no dé
    un WoE infinito.
    """
    cortes = cortes_por_cuantil(valores, grupos) if _es_continua(valores) else None
    datos = pd.DataFrame(
        {"tramo": asignar_tramos(valores, cortes).to_numpy(), "y": np.asarray(y, dtype=float)}
    )
    tabla = datos.groupby("tramo", sort=False).agg(n=("y", "size"), eventos=("y", "sum"))
    tabla["no_eventos"] = tabla["n"] - tabla["eventos"]
    tabla["tasa_evento"] = tabla["eventos"] / tabla["n"]
    eventos = tabla["eventos"] + suavizado
    no_eventos = tabla["no_eventos"] + suavizado
    tabla["pct_eventos"] = eventos / eventos.sum()
    tabla["pct_no_eventos"] = no_eventos / no_eventos.sum()
    tabla["woe"] = np.log(tabla["pct_no_eventos"] / tabla["pct_eventos"])
    tabla["iv"] = (tabla["pct_no_eventos"] - tabla["pct_eventos"]) * tabla["woe"]
    tabla = tabla.reset_index()
    if cortes is not None:  # los intervalos en su orden natural, el faltante al final
        orden = {f: i for i, f in enumerate(asignar_tramos(pd.Series(cortes), cortes))}
        tabla["_orden"] = tabla["tramo"].map(lambda t: orden.get(t, len(cortes) + 1))
        tabla = tabla.sort_values(["_orden", "tramo"]).drop(columns="_orden")
    else:  # códigos numéricos en orden numérico; el resto, alfabético
        tabla = tabla.sort_values("tramo", key=lambda s: s.map(_clave_de_orden))
    return tabla.reset_index(drop=True)


def _clave_de_orden(tramo: str) -> tuple:
    try:
        return (0, float(tramo), "")
    except ValueError:
        return (1, 0.0, str(tramo))


def lectura_iv(iv: float) -> str:
    """Regla usual de lectura del Information Value."""
    if iv < 0.02:
        return "no predictiva"
    if iv < 0.10:
        return "débil"
    if iv < 0.30:
        return "media"
    if iv < 0.50:
        return "fuerte"
    return "muy fuerte (revisar fuga)"


def tabla_deciles(y: np.ndarray, p: np.ndarray, grupos: int = 10) -> pd.DataFrame:
    """Tabla de ganancias: deciles de puntaje, del más riesgoso (1) al menos riesgoso.

    - `tasa_observada`: frecuencia del evento en el decil.
    - `captura_acumulada`: share de todos los eventos que caen en este decil o en los
      más riesgosos.
    - `lift`: tasa del decil sobre la tasa global. `lift_acumulado`, lo mismo para los
      deciles hasta este.

    Los tramos son los mismos de `metricas.tabla_calibracion`, en orden inverso, para que
    las dos tablas repartan igual los puntajes empatados.
    """
    datos = pd.DataFrame({"y": np.asarray(y, dtype=float), "p": np.asarray(p, dtype=float)})
    rango = datos["p"].rank(method="first")
    datos["decil"] = grupos - pd.qcut(rango, grupos, labels=False)
    tabla = datos.groupby("decil").agg(
        n=("y", "size"),
        eventos=("y", "sum"),
        prob_media=("p", "mean"),
        prob_min=("p", "min"),
        prob_max=("p", "max"),
    )
    tasa_global = datos["y"].mean()
    tabla["tasa_observada"] = tabla["eventos"] / tabla["n"]
    tabla["captura_acumulada"] = tabla["eventos"].cumsum() / tabla["eventos"].sum()
    tabla["lift"] = tabla["tasa_observada"] / tasa_global
    tabla["lift_acumulado"] = (tabla["eventos"].cumsum() / tabla["n"].cumsum()) / tasa_global
    return tabla.reset_index()


def curva_ks(y: np.ndarray, p: np.ndarray, puntos: int = 200) -> pd.DataFrame:
    """Distribuciones acumuladas del puntaje con y sin evento, por share de población.

    Se recorre la población del puntaje más alto al más bajo. El KS es la mayor
    distancia vertical entre las dos curvas. Como en `metricas.ks`, con puntajes
    empatados solo cuenta el punto donde termina cada grupo de empates: dentro de un
    empate el orden es arbitrario. El punto de máxima distancia siempre se conserva.
    """
    orden = np.argsort(-np.asarray(p, dtype=float), kind="stable")
    y = np.asarray(y, dtype=float)[orden]
    p = np.asarray(p, dtype=float)[orden]
    con = np.cumsum(y) / y.sum()
    sin = np.cumsum(1 - y) / (1 - y).sum()
    poblacion = np.arange(1, len(y) + 1) / len(y)
    validos = np.flatnonzero(np.append(p[1:] != p[:-1], True))
    muestra = validos[np.unique(np.linspace(0, len(validos) - 1, puntos).round().astype(int))]
    maximo = validos[np.argmax((con - sin)[validos])]
    indices = np.union1d(muestra, [maximo])
    return pd.DataFrame(
        {
            "poblacion": np.concatenate([[0.0], poblacion[indices]]),
            "acumulado_eventos": np.concatenate([[0.0], con[indices]]),
            "acumulado_no_eventos": np.concatenate([[0.0], sin[indices]]),
        }
    ).assign(distancia=lambda t: t["acumulado_eventos"] - t["acumulado_no_eventos"])


def csi(referencia: pd.Series, actual: pd.Series, grupos: int = 10) -> float:
    """Índice de estabilidad de una variable entre dos poblaciones (PSI por variable).

    Las continuas se cortan con los deciles de la referencia; las demás usan sus valores.
    Mismos umbrales que el PSI: 0,10 y 0,25.
    """
    cortes = cortes_por_cuantil(referencia, grupos) if _es_continua(referencia) else None
    a = asignar_tramos(referencia, cortes).value_counts(normalize=True)
    b = asignar_tramos(actual, cortes).value_counts(normalize=True)
    tramos = a.index.union(b.index)
    a = np.clip(a.reindex(tramos, fill_value=0).to_numpy(), 1e-6, None)
    b = np.clip(b.reindex(tramos, fill_value=0).to_numpy(), 1e-6, None)
    return float(((b - a) * np.log(b / a)).sum())


def lectura_psi(valor: float) -> str:
    """Regla usual de lectura del PSI y del CSI."""
    if valor < 0.10:
        return "estable"
    if valor < 0.25:
        return "revisar"
    return "cambio grande"
