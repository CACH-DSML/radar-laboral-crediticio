"""Evalúa los pronosticadores sobre la serie del almacén y publica los resultados.

Deja tres tablas en `marts`:

- `nowcast_evaluacion`: cada pronóstico fuera de muestra, con su error.
- `nowcast_resumen`: el error absoluto medio de cada modelo y su relación con el baseline.
- `nowcast_pronostico`: el nowcast de los trimestres que ya tienen indicadores del BCRP
  pero todavía no tienen empleo de la EPEN.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from radar.nowcast.modelos import (
    Pronosticador,
    error_absoluto_medio,
    evaluar_origen_movil,
    ingenuo,
    ingenuo_estacional,
    puente,
)

OBJETIVOS = ("ocupados_miles", "tasa_informalidad")
# Trimestres que se reservan para entrenar antes del primer pronóstico. Con 16 en total,
# quedan 8 pronósticos fuera de muestra.
INICIO = 8
BASELINE = "ingenuo"
REGRESOR = "puestos_formales_miles"

ESQUEMAS = {
    "nowcast_evaluacion": (
        "objetivo VARCHAR, modelo VARCHAR, fecha DATE, real DOUBLE, pronostico DOUBLE, error DOUBLE"
    ),
    "nowcast_resumen": (
        "objetivo VARCHAR, modelo VARCHAR, pronosticos BIGINT, error_absoluto_medio DOUBLE, "
        "relativo_al_baseline DOUBLE"
    ),
    "nowcast_pronostico": (
        "objetivo VARCHAR, modelo VARCHAR, fecha DATE, horizonte BIGINT, pronostico DOUBLE"
    ),
}


def modelos(objetivo: str) -> dict[str, Pronosticador]:
    """Los modelos que se comparan para un objetivo."""
    return {
        BASELINE: ingenuo(objetivo),
        "ingenuo_estacional": ingenuo_estacional(objetivo),
        "puente_puestos_formales": puente(objetivo, [REGRESOR]),
    }


def evaluar(serie: pd.DataFrame, inicio: int = INICIO) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluación con origen móvil de todos los modelos y objetivos.

    `serie` trae los trimestres con empleo de la EPEN y los tres meses del BCRP.
    Devuelve la tabla de pronósticos y la de resumen.
    """
    evaluaciones, resumen = [], []
    for objetivo in OBJETIVOS:
        errores: dict[str, float] = {}
        for nombre, pronosticador in modelos(objetivo).items():
            evaluacion = evaluar_origen_movil(serie, objetivo, pronosticador, inicio)
            errores[nombre] = error_absoluto_medio(evaluacion)
            evaluaciones.append(
                evaluacion.rename_axis("fecha")
                .reset_index()
                .assign(objetivo=objetivo, modelo=nombre)
            )
        for nombre, error in errores.items():
            resumen.append(
                {
                    "objetivo": objetivo,
                    "modelo": nombre,
                    "pronosticos": len(serie) - inicio,
                    "error_absoluto_medio": error,
                    "relativo_al_baseline": error / errores[BASELINE],
                }
            )
    columnas = ["objetivo", "modelo", "fecha", "real", "pronostico", "error"]
    return pd.concat(evaluaciones, ignore_index=True)[columnas], pd.DataFrame(resumen)


def pronosticar_pendientes(serie: pd.DataFrame, pendientes: pd.DataFrame) -> pd.DataFrame:
    """Nowcast de los trimestres con indicadores del BCRP y sin empleo de la EPEN.

    Se entrena con toda la serie. Solo se usan el baseline y la ecuación puente: el
    baseline estacional está definido a un trimestre de distancia, no a varios.
    """
    filas = []
    for objetivo in OBJETIVOS:
        candidatos = modelos(objetivo)
        for nombre in (BASELINE, "puente_puestos_formales"):
            for horizonte, (fecha, fila) in enumerate(pendientes.iterrows(), start=1):
                filas.append(
                    {
                        "objetivo": objetivo,
                        "modelo": nombre,
                        "fecha": fecha,
                        "horizonte": horizonte,
                        "pronostico": candidatos[nombre](serie, fila),
                    }
                )
    return pd.DataFrame(filas, columns=["objetivo", "modelo", "fecha", "horizonte", "pronostico"])


def publicar(con: duckdb.DuckDBPyConnection, inicio: int = INICIO) -> bool:
    """Crea las tres tablas. Devuelve falso si la serie es muy corta para evaluar.

    Con una serie corta las tablas se crean vacías: el almacén queda completo y las
    consultas no fallan.
    """
    for tabla, esquema in ESQUEMAS.items():
        con.execute(f"CREATE OR REPLACE TABLE marts.{tabla} ({esquema})")

    todo = con.execute("SELECT * FROM marts.nowcast_trimestral ORDER BY fecha").df()
    todo = todo.set_index("fecha")
    completos = todo["meses_bcrp"] == 3
    serie = todo[completos & todo["ocupados_miles"].notna()]
    if len(serie) <= inicio:
        return False

    evaluacion, resumen = evaluar(serie, inicio)  # noqa: F841 (las lee DuckDB)
    con.execute("INSERT INTO marts.nowcast_evaluacion SELECT * FROM evaluacion")
    con.execute("INSERT INTO marts.nowcast_resumen SELECT * FROM resumen")

    posteriores = todo.index > serie.index.max()
    pendientes = todo[completos & todo["ocupados_miles"].isna() & posteriores]
    if len(pendientes):
        pronostico = pronosticar_pendientes(serie, pendientes)  # noqa: F841
        con.execute("INSERT INTO marts.nowcast_pronostico SELECT * FROM pronostico")
    return True
