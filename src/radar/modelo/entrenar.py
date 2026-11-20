"""Entrena, calibra y evalúa el modelo de vulnerabilidad del ingreso.

Hay dos modelos para el mismo evento:

- Un baseline logístico, que es la referencia interpretable.
- Un modelo de boosting (LightGBM), que capta no linealidades e interacciones.

Ambos se entrenan con la primera cohorte, se calibran con la segunda y se evalúan con la
tercera. La calibración es una regresión isotónica: una función creciente que convierte
el puntaje en la probabilidad observada, estimada con datos que el modelo no vio.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from radar.modelo import metricas
from radar.modelo.datos import BOOLEANAS, CATEGORICAS, NUMERICAS, Particion, preparar

SEMILLA = 20261116
PARAMETROS_BOOSTING = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 100,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "n_estimators": 1000,
    "random_state": SEMILLA,
    "n_jobs": 1,  # un solo hilo: el resultado es el mismo en cualquier máquina
    "deterministic": True,
    "force_row_wise": True,
    "verbose": -1,
}
PACIENCIA = 50


@dataclass
class Modelo:
    """Un modelo ya entrenado y calibrado."""

    nombre: str
    estimador: object
    calibrador: IsotonicRegression
    categorias: dict[str, list[str]] = field(default_factory=dict)

    def matriz(self, datos: pd.DataFrame) -> pd.DataFrame:
        x = preparar(datos)
        if self.categorias:  # LightGBM necesita las mismas categorías que al entrenar
            for columna, niveles in self.categorias.items():
                x[columna] = pd.Categorical(x[columna], categories=niveles)
        return x

    def puntaje(self, datos: pd.DataFrame) -> np.ndarray:
        """Puntaje sin calibrar, entre 0 y 1."""
        return self.estimador.predict_proba(self.matriz(datos))[:, 1]

    def probabilidad(self, datos: pd.DataFrame) -> np.ndarray:
        """Probabilidad calibrada del evento."""
        return self.calibrador.predict(self.puntaje(datos))


def _calibrar(puntaje: np.ndarray, y: np.ndarray) -> IsotonicRegression:
    return IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(puntaje, y)


def entrenar_logistico(particion: Particion, objetivo: str) -> Modelo:
    """Baseline: regresión logística con categorías en columnas y números estandarizados."""
    numericas = NUMERICAS + BOOLEANAS
    transformador = ColumnTransformer(
        [
            (
                "numericas",
                Pipeline(
                    [("imputar", SimpleImputer(strategy="median")), ("escalar", StandardScaler())]
                ),
                numericas,
            ),
            (
                "categoricas",
                OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=50),
                CATEGORICAS,
            ),
        ]
    )
    estimador = Pipeline(
        [("transformar", transformador), ("logistica", LogisticRegression(max_iter=2000, C=1.0))]
    )
    estimador.fit(preparar(particion.entrenamiento), particion.entrenamiento[objetivo].astype(int))
    modelo = Modelo("logistico", estimador, IsotonicRegression())
    modelo.calibrador = _calibrar(
        modelo.puntaje(particion.validacion), particion.validacion[objetivo].astype(int)
    )
    return modelo


def entrenar_boosting(particion: Particion, objetivo: str) -> Modelo:
    """LightGBM con parada temprana sobre la cohorte de validación."""
    x = preparar(particion.entrenamiento)
    categorias = {c: sorted(x[c].unique()) for c in CATEGORICAS}
    modelo = Modelo(
        "boosting", lgb.LGBMClassifier(**PARAMETROS_BOOSTING), IsotonicRegression(), categorias
    )
    y_validacion = particion.validacion[objetivo].astype(int)
    modelo.estimador.fit(
        modelo.matriz(particion.entrenamiento),
        particion.entrenamiento[objetivo].astype(int),
        eval_set=[(modelo.matriz(particion.validacion), y_validacion)],
        eval_metric="auc",
        callbacks=[lgb.early_stopping(PACIENCIA, verbose=False)],
    )
    modelo.calibrador = _calibrar(modelo.puntaje(particion.validacion), y_validacion)
    return modelo


def evaluar(modelo: Modelo, particion: Particion, objetivo: str) -> pd.DataFrame:
    """Métricas del modelo calibrado en cada parte. La que cuenta es la de prueba."""
    filas = []
    for parte, datos in (
        ("entrenamiento", particion.entrenamiento),
        ("validacion", particion.validacion),
        ("prueba", particion.prueba),
    ):
        y = datos[objetivo].astype(int).to_numpy()
        filas.append({"parte": parte, **metricas.resumen(y, modelo.probabilidad(datos))})
    tabla = pd.DataFrame(filas)
    tabla.insert(0, "modelo", modelo.nombre)
    tabla.insert(0, "objetivo", objetivo)
    return tabla


def importancia(modelo: Modelo, datos: pd.DataFrame) -> pd.DataFrame:
    """Importancia de cada variable según los valores SHAP del modelo de boosting.

    LightGBM calcula los valores SHAP exactos de sus árboles (`pred_contrib`). Para cada
    persona reparten su puntaje entre las variables. La importancia de una variable es el
    promedio del valor absoluto de su contribución, en la escala del logaritmo de la razón
    de probabilidades.
    """
    contribuciones = modelo.estimador.booster_.predict(modelo.matriz(datos), pred_contrib=True)
    variables = modelo.estimador.booster_.feature_name()
    tabla = pd.DataFrame(
        {"variable": variables, "shap_medio_absoluto": np.abs(contribuciones[:, :-1]).mean(axis=0)}
    ).sort_values("shap_medio_absoluto", ascending=False, ignore_index=True)
    tabla["participacion"] = tabla["shap_medio_absoluto"] / tabla["shap_medio_absoluto"].sum()
    return tabla


def estabilidad(modelo: Modelo, particion: Particion) -> pd.DataFrame:
    """PSI de la probabilidad estimada entre la cohorte de entrenamiento y las siguientes."""
    referencia = modelo.probabilidad(particion.entrenamiento)
    return pd.DataFrame(
        [
            {
                "modelo": modelo.nombre,
                "comparacion": f"entrenamiento contra {parte}",
                "psi": metricas.psi(referencia, modelo.probabilidad(datos)),
            }
            for parte, datos in (("validacion", particion.validacion), ("prueba", particion.prueba))
        ]
    )


def auditar_por_grupo(
    modelo: Modelo, datos: pd.DataFrame, objetivo: str, columna: str
) -> pd.DataFrame:
    """Compara lo estimado con lo observado en los grupos de una variable que el modelo
    no usa. Sirve para ver si el modelo trata distinto a un grupo."""
    p = modelo.probabilidad(datos)
    y = datos[objetivo].astype(int).to_numpy()
    filas = []
    for grupo in sorted(datos[columna].dropna().unique()):
        es = (datos[columna] == grupo).to_numpy()
        filas.append(
            {
                "variable": columna,
                "grupo": str(grupo),
                "n": int(es.sum()),
                "observado": float(y[es].mean()),
                "estimado": float(p[es].mean()),
                "auc": metricas.auc(y[es], p[es]),
            }
        )
    return pd.DataFrame(filas)
