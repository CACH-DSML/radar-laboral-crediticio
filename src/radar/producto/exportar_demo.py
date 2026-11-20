"""Exporta la base de demo: solo las tablas agregadas que leen la API y la aplicación.

Uso:
    python -m radar.producto.exportar_demo

Lee el almacén completo (`data/radar.duckdb`) y escribe `dashboard/radar_demo.duckdb`. La base
de demo no tiene las capas `raw` ni `staging` de microdatos: solo indicadores, puntajes,
resultados del modelo, el resumen agregado de sus variables y el catálogo de grandes
grupos de ocupación. Antes de terminar
verifica que ninguna celda suprimida lleve valor, que ninguna columna venga de la tabla
de personas y que el archivo pese menos de 50 MB. Si algo falla, borra el archivo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from radar.config import RAIZ, ruta_almacen
from radar.producto.resumen_variables import MINIMO_TRAMO, resumir

DESTINO = RAIZ / "dashboard" / "radar_demo.duckdb"
TAMANIO_MAXIMO = 50 * 1024 * 1024

# Lo que leen `radar.producto.vistas` y `radar.api.app`. Nada más.
TABLAS: dict[str, tuple[str, ...]] = {
    "marts": (
        "indicadores",
        "score_segmento",
        "modelo_metricas",
        "modelo_auditoria",
        "modelo_calibracion",
        "modelo_importancia",
        "modelo_estabilidad",
    ),
    # Catálogo público de la CNO 2015 (código y nombre del gran grupo); lo usa
    # `vistas.tabla_score` para nombrar las ocupaciones.
    "staging": ("cno_grandes_grupos",),
}
# Resumen de las variables del modelo (`resumen_variables`): se calcula aquí a partir del
# panel y solo se guardan sus agregados.
DERIVADAS: dict[str, str] = {
    "variables_tramos": (
        "variable VARCHAR, orden INTEGER, tramo VARCHAR, n BIGINT, tasa_evento DOUBLE"
    ),
    "variables_iv": "variable VARCHAR, iv DOUBLE",
    "variables_correlaciones": "variable_1 VARCHAR, variable_2 VARCHAR, correlacion DOUBLE",
}
# Columnas que pueden compartir las tablas agregadas con la tabla de personas: son las
# llaves de los segmentos, no datos de una persona.
LLAVES_DE_SEGMENTO = {"anio", "ccdd", "rama_inei", "ciiu_seccion", "ocupacion_gran_grupo"}
# Columnas de valor que deben quedar vacías en una celda suprimida.
VALORES_SUPRIMIBLES = {"indicadores": ("valor", "ee", "cv"), "score_segmento": ("score", "ee")}


class DemoInvalida(Exception):
    """La base de demo no cumple alguna de las verificaciones."""


def exportar(origen: Path, destino: Path = DESTINO) -> dict[str, int]:
    """Copia las tablas de `TABLAS` a una base nueva y la verifica. Devuelve filas por tabla."""
    if not origen.is_file():
        raise FileNotFoundError(
            f"No existe el almacén {origen}. Ejecuta `python -m radar.pipeline`."
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.unlink(missing_ok=True)
    try:
        con = duckdb.connect(str(destino))
        try:
            con.execute(f"ATTACH '{origen.as_posix()}' AS fuente (READ_ONLY)")
            filas = {}
            for esquema, tablas in TABLAS.items():
                con.execute(f"CREATE SCHEMA IF NOT EXISTS {esquema}")
                for tabla in tablas:
                    con.execute(
                        f"CREATE TABLE {esquema}.{tabla} AS SELECT * FROM fuente.{esquema}.{tabla}"
                    )
                    filas[f"{esquema}.{tabla}"] = con.execute(
                        f"SELECT count(*) FROM {esquema}.{tabla}"
                    ).fetchone()[0]
            panel = con.execute("SELECT * FROM fuente.marts.panel_12m").df()
            for nombre, datos in resumir(panel).items():
                tabla = f"variables_{nombre}"
                con.execute(f"CREATE TABLE marts.{tabla} ({DERIVADAS[tabla]})")
                if len(datos):
                    con.register("datos", datos)
                    con.execute(f"INSERT INTO marts.{tabla} SELECT * FROM datos")
                    con.unregister("datos")
                filas[f"marts.{tabla}"] = len(datos)
            del panel
            columnas_de_personas = {
                fila[0]
                for fila in con.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_catalog = 'fuente' AND table_schema = 'marts' "
                    "AND table_name = 'epen_pet'"
                ).fetchall()
            }
            con.execute("DETACH fuente")
            verificar(con, columnas_de_personas - LLAVES_DE_SEGMENTO)
            con.execute("CHECKPOINT")
        finally:
            con.close()
        tamanio = destino.stat().st_size
        if tamanio >= TAMANIO_MAXIMO:
            raise DemoInvalida(f"La base de demo pesa {tamanio / 1e6:.1f} MB; el máximo es 50 MB.")
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
    return filas


def verificar(con: duckdb.DuckDBPyConnection, columnas_prohibidas: set[str]) -> None:
    """Falla si la base tiene tablas de más, celdas suprimidas con valor o columnas de personas."""
    presentes = {
        (esquema, tabla)
        for esquema, tabla in con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_catalog = current_database()"
        ).fetchall()
    }
    esperadas = {(esquema, tabla) for esquema, tablas in TABLAS.items() for tabla in tablas}
    esperadas |= {("marts", tabla) for tabla in DERIVADAS}
    if presentes != esperadas:
        raise DemoInvalida(f"Tablas inesperadas: {sorted(presentes ^ esperadas)}")

    for esquema, tabla in sorted(esperadas):
        columnas = {
            fila[0]
            for fila in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_catalog = current_database() AND table_schema = ? "
                "AND table_name = ?",
                [esquema, tabla],
            ).fetchall()
        }
        sobrantes = columnas & columnas_prohibidas
        if sobrantes:
            raise DemoInvalida(f"{esquema}.{tabla} tiene columnas de personas: {sorted(sobrantes)}")

    for tabla, columnas in VALORES_SUPRIMIBLES.items():
        con_valor = " OR ".join(f"{c} IS NOT NULL" for c in columnas)
        indebidas = con.execute(
            f"SELECT count(*) FROM marts.{tabla} WHERE calidad = 'suprimida' AND ({con_valor})"
        ).fetchone()[0]
        if indebidas:
            raise DemoInvalida(f"marts.{tabla}: {indebidas} celdas suprimidas llevan valor")

    pequenos = con.execute(
        f"SELECT count(*) FROM marts.variables_tramos WHERE n < {MINIMO_TRAMO} "
        "AND tasa_evento IS NOT NULL"
    ).fetchone()[0]
    if pequenos:
        raise DemoInvalida(f"marts.variables_tramos: {pequenos} tramos pequeños llevan tasa")


def main() -> int:
    filas = exportar(ruta_almacen())
    print(f"Base de demo: {DESTINO}")
    print(f"Tamaño: {DESTINO.stat().st_size / 1024 / 1024:.2f} MB")
    for tabla, n in filas.items():
        print(f"  {tabla}: {n:,} filas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
