"""Entrena el modelo con el panel del almacén y publica sus resultados.

Tablas que deja en `marts`:

- `modelo_metricas`:          AUC, KS, Brier y error de calibración por modelo y parte.
- `modelo_estabilidad`:       PSI del puntaje entre cohortes.
- `modelo_calibracion`:       estimado contra observado por tramos, en la cohorte de prueba.
- `modelo_importancia`:       importancia de cada variable (valores SHAP).
- `modelo_auditoria`:         estimado contra observado por sexo, variable que no se usa.
- `score_segmento`:           puntaje promedio de cada segmento laboral del último año.
- `modelo_validacion_externa`: puntaje por departamento junto a la morosidad aproximada.
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from radar.indicadores.datos import cargar_pet
from radar.indicadores.estimacion import Estimacion, estimar_por_grupo
from radar.indicadores.parametros import DISENO_EPEN, REGLA_EPEN
from radar.indicadores.supresion import clasificar
from radar.modelo import entrenar, metricas
from radar.modelo.datos import (
    OBJETIVO_CONTRASTE,
    OBJETIVO_PRINCIPAL,
    OBJETIVOS,
    partir_por_cohorte,
)

# Mínimo de personas por cohorte para entrenar. Con menos, las tablas quedan vacías.
MINIMO_POR_COHORTE = 1000

DESAGREGACIONES_SCORE: dict[str, list[str]] = {
    "nacional": [],
    "departamento": ["ccdd"],
    "rama": ["rama_inei"],
    "ocupacion": ["ocupacion_gran_grupo"],
    "departamento_rama": ["ccdd", "rama_inei"],
    "departamento_ocupacion": ["ccdd", "ocupacion_gran_grupo"],
}

ESQUEMAS = {
    "modelo_metricas": (
        "objetivo VARCHAR, modelo VARCHAR, parte VARCHAR, n DOUBLE, tasa_observada DOUBLE, "
        "auc DOUBLE, ks DOUBLE, brier DOUBLE, error_calibracion DOUBLE"
    ),
    "modelo_estabilidad": "objetivo VARCHAR, modelo VARCHAR, comparacion VARCHAR, psi DOUBLE",
    "modelo_calibracion": (
        "objetivo VARCHAR, tramo BIGINT, n BIGINT, estimado DOUBLE, observado DOUBLE"
    ),
    "modelo_importancia": (
        "objetivo VARCHAR, variable VARCHAR, shap_medio_absoluto DOUBLE, participacion DOUBLE"
    ),
    "modelo_auditoria": (
        "objetivo VARCHAR, variable VARCHAR, grupo VARCHAR, n BIGINT, observado DOUBLE, "
        "estimado DOUBLE, auc DOUBLE"
    ),
    "score_segmento": (
        "anio INTEGER, objetivo VARCHAR, desagregacion VARCHAR, ccdd VARCHAR, "
        "rama_inei VARCHAR, ocupacion_gran_grupo VARCHAR, score DOUBLE, ee DOUBLE, "
        "n BIGINT, n_upm BIGINT, calidad VARCHAR"
    ),
    "modelo_validacion_externa": (
        "anio INTEGER, ccdd VARCHAR, departamento VARCHAR, score DOUBLE, "
        "score_contraste DOUBLE, tasa_informalidad DOUBLE, morosidad_proxy_pct DOUBLE"
    ),
}


def puntuar_segmentos(
    pet: pd.DataFrame, probabilidades: dict[str, np.ndarray], poblacion: pd.Series
) -> pd.DataFrame:
    """Puntaje promedio de cada segmento, en porcentaje, con su error estándar.

    El puntaje de un segmento es el promedio de la probabilidad estimada de sus
    ocupados, ponderado por el factor de expansión. El error estándar refleja el
    muestreo de la encuesta, no la incertidumbre del modelo.
    """
    partes = []
    for objetivo, probabilidad in probabilidades.items():
        muestra = pet.assign(_probabilidad=np.where(poblacion, probabilidad, 0.0))
        for nombre, por in DESAGREGACIONES_SCORE.items():
            celdas = estimar_por_grupo(
                muestra, "media", "_probabilidad", por, DISENO_EPEN, dominio=poblacion
            )
            celdas["objetivo"] = objetivo
            celdas["desagregacion"] = nombre
            partes.append(celdas)
    tabla = pd.concat(partes, ignore_index=True)
    tabla["calidad"] = [
        clasificar(Estimacion(f.valor, f.ee, int(f.n), int(f.n_upm)), REGLA_EPEN)
        for f in tabla.itertuples()
    ]
    tabla["score"] = 100 * tabla["valor"]
    tabla["ee"] = 100 * tabla["ee"]
    tabla.loc[tabla["calidad"] == "suprimida", ["score", "ee"]] = float("nan")
    tabla["anio"] = int(pet["anio"].iloc[0])
    return tabla.reindex(
        columns=[
            "anio", "objetivo", "desagregacion", "ccdd", "rama_inei", "ocupacion_gran_grupo",
            "score", "ee", "n", "n_upm", "calidad",
        ]
    )  # fmt: skip


def _insertar(con: duckdb.DuckDBPyConnection, tabla: str, datos: pd.DataFrame) -> None:
    columnas = [parte.split()[0] for parte in ESQUEMAS[tabla].split(", ")]
    ordenado = datos.reindex(columns=columnas)  # noqa: F841 (lo lee DuckDB)
    con.execute(f"INSERT INTO marts.{tabla} SELECT * FROM ordenado")


def publicar(con: duckdb.DuckDBPyConnection) -> bool:
    """Crea las tablas del modelo. Devuelve falso si no hay panel suficiente para entrenar."""
    for tabla, esquema in ESQUEMAS.items():
        con.execute(f"CREATE OR REPLACE TABLE marts.{tabla} ({esquema})")

    panel = con.execute("SELECT * FROM marts.panel_12m").df()
    por_cohorte = panel.groupby("anio_origen").size() if len(panel) else pd.Series(dtype=int)
    if len(por_cohorte) < 3 or por_cohorte.min() < MINIMO_POR_COHORTE:
        return False
    particion = partir_por_cohorte(panel)

    modelos_finales = {}
    for objetivo in OBJETIVOS:
        logistico = entrenar.entrenar_logistico(particion, objetivo)
        boosting = entrenar.entrenar_boosting(particion, objetivo)
        modelos_finales[objetivo] = boosting
        for modelo in (logistico, boosting):
            _insertar(con, "modelo_metricas", entrenar.evaluar(modelo, particion, objetivo))
            _insertar(
                con, "modelo_estabilidad",
                entrenar.estabilidad(modelo, particion).assign(objetivo=objetivo),
            )  # fmt: skip
        prueba = particion.prueba
        y = prueba[objetivo].astype(int).to_numpy()
        _insertar(
            con, "modelo_calibracion",
            metricas.tabla_calibracion(y, boosting.probabilidad(prueba)).assign(objetivo=objetivo),
        )  # fmt: skip
        _insertar(
            con,
            "modelo_importancia",
            entrenar.importancia(boosting, prueba).assign(objetivo=objetivo),
        )
        auditoria = entrenar.auditar_por_grupo(boosting, prueba, objetivo, "sexo")
        _insertar(con, "modelo_auditoria", auditoria.assign(objetivo=objetivo))

    # Puntaje de los ocupados con ingreso del último año de la encuesta.
    anio = int(con.execute("SELECT max(anio) FROM marts.epen_pet").fetchone()[0])
    pet = cargar_pet(anio, con=con)
    poblacion = pet["ocupado"] & (pet["ingreso_total"] > 0)
    ocupados = pet[poblacion]
    probabilidades = {}
    for objetivo in (OBJETIVO_PRINCIPAL, OBJETIVO_CONTRASTE):
        completa = np.zeros(len(pet))
        completa[poblacion.to_numpy()] = modelos_finales[objetivo].probabilidad(ocupados)
        probabilidades[objetivo] = completa
    _insertar(con, "score_segmento", puntuar_segmentos(pet, probabilidades, poblacion))

    con.execute(
        """
        INSERT INTO marts.modelo_validacion_externa
        SELECT s.anio, s.ccdd, d.departamento, s.score, c.score, i.valor, m.morosidad_proxy_pct
        FROM marts.score_segmento AS s
        INNER JOIN staging.dim_departamento AS d ON s.ccdd = d.ccdd
        LEFT JOIN marts.score_segmento AS c
            ON c.anio = s.anio AND c.ccdd = s.ccdd AND c.desagregacion = 'departamento'
            AND c.objetivo = ?
        LEFT JOIN marts.indicadores AS i
            ON i.anio = s.anio AND i.ccdd = s.ccdd AND i.desagregacion = 'departamento'
            AND i.indicador = 'tasa_informalidad'
        LEFT JOIN marts.sbs_morosidad_proxy_departamento AS m
            ON m.anio = s.anio AND m.ccdd = s.ccdd
        WHERE s.desagregacion = 'departamento' AND s.objetivo = ?
        """,
        [OBJETIVO_CONTRASTE, OBJETIVO_PRINCIPAL],
    )
    return True
