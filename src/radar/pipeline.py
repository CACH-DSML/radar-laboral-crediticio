"""Reconstruye el almacén completo con un solo comando.

Uso:
    python -m radar.pipeline                 descarga BCRP y SBS, lee la EPEN y reconstruye todo
    python -m radar.pipeline --sin-descarga  no descarga; usa lo que ya está en data/raw

Las bases de la EPEN no se descargan: se leen de la carpeta EPEN (ver radar.config).
"""

from __future__ import annotations

import argparse
import sys

from radar.almacen.construir import construir, ejecutar_pruebas, leer_raw
from radar.config import VAR_ENTORNO_EPEN, dir_epen, dir_raw, ruta_almacen
from radar.epen.esquema import ANIOS_ESPERADOS
from radar.ingesta import bcrp, epen, sbs
from radar.ingesta.descarga import guardar_manifiesto
from radar.modelo.base import exportar_base


def descargar_todo() -> None:
    carpeta = dir_raw()
    carpeta.mkdir(parents=True, exist_ok=True)
    procedencia: dict[str, dict] = {}
    for grupo in bcrp.GRUPOS:
        print(f"Descargando BCRP: {grupo}")
        procedencia.update(bcrp.descargar_grupo(grupo, carpeta))
    print("Descargando SBS: créditos directos por departamento")
    procedencia.update(sbs.descargar_creditos_departamento(carpeta))
    print("Descargando SBS: indicadores financieros por banco")
    procedencia.update(sbs.descargar_indicadores(carpeta))
    ruta = guardar_manifiesto(carpeta, procedencia)
    print(f"{len(procedencia)} archivos descargados. Procedencia en {ruta}")


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sin-descarga",
        action="store_true",
        help="no descarga; usa los archivos que ya están en data/raw",
    )
    opciones = parser.parse_args(argumentos)

    if not dir_epen().is_dir() or not epen.archivos_dta(dir_epen()):
        print(f"No hay archivos .dta de la EPEN en {dir_epen()}.")
        print(f"Copia ahí las bases anuales o define {VAR_ENTORNO_EPEN}. Ver data/README.md.")
        return 1

    if not opciones.sin_descarga:
        descargar_todo()

    print(f"EPEN: leyendo {dir_epen()}")
    parquets_epen = epen.preparar(dir_epen(), dir_raw())
    sin_cubrir = [anio for anio in ANIOS_ESPERADOS if anio not in parquets_epen]
    if sin_cubrir:
        print(f"Faltan las bases de la EPEN de: {sin_cubrir}")
        return 1

    print(f"Construyendo {ruta_almacen()}")
    con = construir(ruta_almacen(), leer_raw(dir_raw(), parquets_epen))

    print("\nTablas:")
    tablas = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "ORDER BY table_schema, table_name"
    ).fetchall()
    for esquema, tabla in tablas:
        filas = con.execute(f"SELECT count(*) FROM {esquema}.{tabla}").fetchone()[0]
        print(f"  {esquema}.{tabla}: {filas:,} filas")

    print("\nPruebas de calidad (filas que violan la regla):")
    resultados = ejecutar_pruebas(con)
    for nombre, violaciones in resultados.items():
        print(f"  {'OK   ' if violaciones == 0 else 'FALLA'} {nombre}: {violaciones}")

    print("\nAdvertencias (anomalías de las fuentes, no detienen el pipeline):")
    for nombre, filas in ejecutar_pruebas(con, "advertencias").items():
        print(f"  {nombre}: {filas} filas")
    fallas = sum(1 for violaciones in resultados.values() if violaciones)
    if fallas == 0:
        print(f"\nBase final del modelo: {exportar_base(con)}")
    con.close()

    print(f"\nResultado: {'OK' if fallas == 0 else f'{fallas} pruebas con fallas'}")
    return 0 if fallas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
