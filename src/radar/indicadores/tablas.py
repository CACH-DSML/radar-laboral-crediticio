"""Tablas de indicadores laborales por departamento, sector y ocupación.

Cada fila de la tabla final es una celda: un indicador, en un año, para un grupo. Trae
el valor, su error estándar, la muestra que lo respalda y si se puede publicar.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import duckdb
import pandas as pd

from radar.indicadores.datos import cargar_pet
from radar.indicadores.estimacion import Diseno, Estadistico, Estimacion, estimar_por_grupo
from radar.indicadores.parametros import DISENO_EPEN, REGLA_EPEN
from radar.indicadores.supresion import ReglaSupresion, clasificar

HORAS_JORNADA_COMPLETA = 35
SIN_CLASIFICAR = "(sin clasificar)"


@dataclass(frozen=True)
class Indicador:
    """Cómo se calcula un indicador.

    estadistico:  qué se estima (total, media, proporción o mediana).
    columna:      sobre qué columna de la muestra.
    dominio:      quiénes entran: recibe la muestra y devuelve una serie booleana.
    escala:       factor por el que se multiplican el valor y su error (100 en las tasas).
    """

    nombre: str
    unidad: str
    estadistico: Estadistico
    columna: str
    dominio: Callable[[pd.DataFrame], pd.Series]
    escala: float = 1.0


def _ocupados(pet: pd.DataFrame) -> pd.Series:
    return pet["ocupado"]


def _ocupados_con_ingreso(pet: pd.DataFrame) -> pd.Series:
    # El INEI promedia el ingreso entre quienes lo tienen: deja fuera a los trabajadores
    # familiares no remunerados, que figuran con ingreso cero.
    return pet["ocupado"] & (pet["ingreso_total"] > 0)


INDICADORES: tuple[Indicador, ...] = (
    Indicador("ocupados", "personas", "total", "uno", _ocupados),
    Indicador("tasa_informalidad", "porcentaje", "proporcion", "informal", _ocupados, 100.0),
    Indicador(
        "tasa_afiliacion_pension", "porcentaje", "proporcion", "afiliado_pension", _ocupados, 100.0
    ),
    # Solo el subempleo por horas: el de ingresos no se puede reproducir con la base.
    Indicador(
        "tasa_subempleo_horas", "porcentaje", "proporcion", "subempleo_horas", _ocupados, 100.0
    ),
    Indicador("ingreso_promedio", "soles", "media", "ingreso_total", _ocupados_con_ingreso),
    Indicador("ingreso_mediano", "soles", "mediana", "ingreso_total", _ocupados_con_ingreso),
)

# Nombre de la desagregación -> columnas que la definen.
DESAGREGACIONES: dict[str, list[str]] = {
    "nacional": [],
    "departamento": ["ccdd"],
    "rama": ["rama_inei"],
    "seccion": ["ciiu_seccion"],
    "ocupacion": ["ocupacion_gran_grupo"],
    "departamento_rama": ["ccdd", "rama_inei"],
    "departamento_seccion": ["ccdd", "ciiu_seccion"],
    "departamento_ocupacion": ["ccdd", "ocupacion_gran_grupo"],
    "departamento_seccion_ocupacion": ["ccdd", "ciiu_seccion", "ocupacion_gran_grupo"],
}
COLUMNAS_DE_GRUPO = ["ccdd", "rama_inei", "ciiu_seccion", "ocupacion_gran_grupo"]
COLUMNAS = [
    "anio",
    "desagregacion",
    *COLUMNAS_DE_GRUPO,
    "indicador",
    "unidad",
    "valor",
    "ee",
    "cv",
    "n",
    "n_upm",
    "calidad",
]
TIPOS = {
    "anio": "INTEGER",
    "desagregacion": "VARCHAR",
    "ccdd": "VARCHAR",
    "rama_inei": "VARCHAR",
    "ciiu_seccion": "VARCHAR",
    "ocupacion_gran_grupo": "VARCHAR",
    "indicador": "VARCHAR",
    "unidad": "VARCHAR",
    "valor": "DOUBLE",
    "ee": "DOUBLE",
    "cv": "DOUBLE",
    "n": "BIGINT",
    "n_upm": "BIGINT",
    "calidad": "VARCHAR",
}


def preparar_muestra(pet: pd.DataFrame) -> pd.DataFrame:
    """Agrega las columnas derivadas que usan los indicadores.

    Un ocupado sin departamento, sector u ocupación (un código que no está en el
    catálogo) no se descarta ni detiene el cálculo: queda en un grupo visible,
    "(sin clasificar)", que las pruebas de calidad del almacén marcan como error.
    """
    grupos = {
        columna: pet[columna]
        .astype(object)
        .where(pet[columna].notna() | ~pet["ocupado"], SIN_CLASIFICAR)
        for columna in COLUMNAS_DE_GRUPO
    }
    return pet.assign(
        **grupos,
        uno=1.0,
        subempleo_horas=(
            pet["ocupado"]
            & (pet["horas_semana"] < HORAS_JORNADA_COMPLETA)
            & pet["quiere_mas_horas"]
        ),
    )


def calcular_indicadores(
    pet: pd.DataFrame,
    diseno: Diseno = DISENO_EPEN,
    regla: ReglaSupresion = REGLA_EPEN,
    desagregaciones: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Todos los indicadores de un año, en todas las desagregaciones.

    `pet` es la muestra completa de un solo año (ver `cargar_pet`). En una celda
    suprimida el valor, el error estándar y el coeficiente de variación quedan nulos; el
    tamaño de la muestra se conserva para que se vea por qué se suprimió.
    """
    anios = pet["anio"].unique()
    if len(anios) != 1:
        raise ValueError(f"Se esperaba la muestra de un solo año y hay {sorted(anios)}")
    muestra = preparar_muestra(pet)

    partes = []
    for nombre, por in (desagregaciones or DESAGREGACIONES).items():
        for indicador in INDICADORES:
            celdas = estimar_por_grupo(
                muestra,
                indicador.estadistico,
                indicador.columna,
                por,
                diseno,
                dominio=indicador.dominio(muestra),
            )
            celdas["valor"] *= indicador.escala
            celdas["ee"] *= indicador.escala
            celdas["desagregacion"] = nombre
            celdas["indicador"] = indicador.nombre
            celdas["unidad"] = indicador.unidad
            partes.append(celdas)

    tabla = pd.concat(partes, ignore_index=True)
    tabla["anio"] = int(anios[0])
    estimaciones = [
        Estimacion(valor=fila.valor, ee=fila.ee, n=int(fila.n), n_upm=int(fila.n_upm))
        for fila in tabla.itertuples()
    ]
    tabla["cv"] = [estimacion.cv for estimacion in estimaciones]
    tabla["calidad"] = [clasificar(estimacion, regla) for estimacion in estimaciones]
    tabla.loc[tabla["calidad"] == "suprimida", ["valor", "ee", "cv"]] = float("nan")
    return tabla.reindex(columns=COLUMNAS)


def publicar(con: duckdb.DuckDBPyConnection) -> int:
    """Calcula los indicadores de cada año del almacén y los deja en `marts.indicadores`.

    Devuelve el número de celdas.
    """
    columnas = ", ".join(f"{nombre} {tipo}" for nombre, tipo in TIPOS.items())
    con.execute(f"CREATE OR REPLACE TABLE marts.indicadores ({columnas})")
    anios = [
        anio
        for (anio,) in con.execute(
            "SELECT DISTINCT anio FROM marts.epen_pet WHERE tiene_factor ORDER BY anio"
        ).fetchall()
    ]
    for anio in anios:
        tabla = calcular_indicadores(cargar_pet(anio, con=con))  # noqa: F841 (la lee DuckDB)
        con.execute("INSERT INTO marts.indicadores SELECT * FROM tabla")
    return con.execute("SELECT count(*) FROM marts.indicadores").fetchone()[0]
