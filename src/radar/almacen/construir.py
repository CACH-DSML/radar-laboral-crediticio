"""Construye el almacén DuckDB desde cero a partir de las tablas crudas.

Capas:
- raw:     filas tal como las entrega cada fuente, todo en texto o sin tipar.
- staging: tipos, fechas y llaves limpias; una tabla por fuente, más los catálogos.
- marts:   tablas listas para análisis. Incluye los indicadores con error estándar y
           el nowcast, que se calculan en Python después de las tablas en SQL.

Las transformaciones son archivos SQL numerados que se ejecutan en orden. Las pruebas de
calidad son consultas que devuelven las filas que violan una regla: cero filas es éxito.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from radar.indicadores import tablas
from radar.ingesta import bcrp, epen, sbs
from radar.modelo import publicar as modelo
from radar.nowcast import publicar as nowcast

DIR_SQL = Path(__file__).parent / "sql"
DIR_SEMILLAS = Path(__file__).parent / "semillas"
RUTA_DEPARTAMENTOS = DIR_SEMILLAS / "departamentos.csv"
# Catálogos versionados en el repositorio: tabla de staging -> archivo CSV.
SEMILLAS = {
    "dim_departamento": "departamentos.csv",
    "ciiu_rev4": "ciiu_rev4.csv",
    "cno_grandes_grupos": "cno_2015_grandes_grupos.csv",
    "epen_cifras_oficiales": "epen_cifras_oficiales.csv",
    "epen_cifras_oficiales_trimestrales": "epen_cifras_oficiales_trimestrales.csv",
}

# Una tabla cruda llega como DataFrame o como lista de archivos Parquet.
TablaRaw = pd.DataFrame | list[Path]


def leer_raw(dir_raw: Path, parquets_epen: dict[int, Path]) -> dict[str, TablaRaw]:
    """Reúne las tablas crudas: BCRP y SBS ya descargados, y la EPEN ya convertida."""
    filas_bcrp = [fila for grupo in bcrp.GRUPOS for fila in bcrp.leer_grupo(grupo, dir_raw)]
    variables, etiquetas = epen.leer_metadatos(dir_raw, list(parquets_epen))
    return {
        "bcrp_observaciones": pd.DataFrame(filas_bcrp, columns=bcrp.COLUMNAS),
        "sbs_creditos_departamento": pd.DataFrame(
            sbs.leer_creditos_departamento(dir_raw), columns=sbs.COLUMNAS
        ),
        "sbs_morosidad_banco": pd.DataFrame(
            sbs.leer_morosidad_por_banco(dir_raw), columns=sbs.COLUMNAS_MOROSIDAD
        ),
        "epen": list(parquets_epen.values()),
        "epen_variables": variables,
        "epen_etiquetas": etiquetas,
    }


def _ejecutar_carpeta(con: duckdb.DuckDBPyConnection, carpeta: str) -> list[str]:
    ejecutados = []
    for ruta in sorted((DIR_SQL / carpeta).glob("*.sql")):
        con.execute(ruta.read_text(encoding="utf-8"))
        ejecutados.append(ruta.name)
    return ejecutados


def construir(
    ruta_db: Path,
    tablas_raw: dict[str, TablaRaw],
    semillas: dict[str, Path] | None = None,
) -> duckdb.DuckDBPyConnection:
    """Borra el almacén anterior y lo reconstruye. Devuelve la conexión abierta.

    `semillas` reemplaza catálogos por otros archivos CSV; lo usan los tests.
    """
    ruta_db.parent.mkdir(parents=True, exist_ok=True)
    for sobrante in (ruta_db, ruta_db.with_name(ruta_db.name + ".wal")):
        sobrante.unlink(missing_ok=True)

    con = duckdb.connect(str(ruta_db))
    for esquema in ("raw", "staging", "marts"):
        con.execute(f"CREATE SCHEMA {esquema}")

    for nombre, tabla in tablas_raw.items():
        if isinstance(tabla, pd.DataFrame):
            con.register("_tabla_entrante", tabla)
            con.execute(f"CREATE TABLE raw.{nombre} AS SELECT * FROM _tabla_entrante")
            con.unregister("_tabla_entrante")
        else:
            # Las columnas se unen por nombre: no todos los años traen las mismas.
            con.execute(
                f"CREATE TABLE raw.{nombre} AS SELECT * FROM read_parquet(?, union_by_name = true)",
                [[str(ruta) for ruta in tabla]],
            )

    rutas_semillas = {nombre: DIR_SEMILLAS / archivo for nombre, archivo in SEMILLAS.items()}
    rutas_semillas.update(semillas or {})
    for nombre, ruta in rutas_semillas.items():
        con.execute(
            f"CREATE TABLE staging.{nombre} AS "
            "SELECT * FROM read_csv(?, header = true, all_varchar = true)",
            [str(ruta)],
        )

    _ejecutar_carpeta(con, "staging")
    _ejecutar_carpeta(con, "marts")

    # Productos que no son SQL: se calculan en Python sobre las tablas anteriores.
    tablas.publicar(con)
    nowcast.publicar(con)
    modelo.publicar(con)
    return con


def ejecutar_pruebas(con: duckdb.DuckDBPyConnection, carpeta: str = "pruebas") -> dict[str, int]:
    """Ejecuta cada consulta de la carpeta. Devuelve cuántas filas devuelve cada una.

    `pruebas` son reglas que deben dar cero filas. `advertencias` son anomalías conocidas
    de las fuentes: se informan, pero no invalidan el almacén.
    """
    resultados = {}
    for ruta in sorted((DIR_SQL / carpeta).glob("*.sql")):
        consulta = ruta.read_text(encoding="utf-8").strip().rstrip(";")
        resultados[ruta.stem] = con.execute(f"SELECT count(*) FROM ({consulta})").fetchone()[0]
    return resultados
