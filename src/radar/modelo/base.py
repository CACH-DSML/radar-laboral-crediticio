"""Base final del modelo en CSV.

Es la tabla `marts.panel_12m` del almacén escrita como archivo plano: una fila por
persona, con sus variables en la primera visita y lo que le pasó 12 meses después. Con
ella se hace el análisis y se entrena el modelo.

Uso:
    python -m radar.modelo.base      escribe data/base_modelo.csv desde el almacén

El pipeline (`python -m radar.pipeline`) también la escribe al terminar. Son microdatos
de personas: el archivo se queda en la computadora y no se sube al repositorio.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

from radar.config import ruta_almacen, ruta_base_modelo

# Columnas de texto. Se leen como texto para no perder ceros iniciales: el departamento
# "01" no es el número 1.
COLUMNAS_TEXTO = [
    "llave_panel", "conglomerado", "ccdd", "departamento", "area_nombre", "sexo",
    "ocupacion_gran_grupo", "ciiu_seccion", "rama_inei",
]  # fmt: skip


def exportar_base(con: duckdb.DuckDBPyConnection, destino: Path | None = None) -> Path:
    """Escribe `marts.panel_12m` en CSV, en el mismo orden de filas que el almacén."""
    destino = destino or ruta_base_modelo()
    texto = {
        nombre
        for nombre, tipo in con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'marts' AND table_name = 'panel_12m'"
        ).fetchall()
        if tipo == "VARCHAR"
    }
    if texto != set(COLUMNAS_TEXTO):
        raise ValueError(
            f"Cambiaron las columnas de texto de marts.panel_12m: {sorted(texto)}. "
            "Actualiza COLUMNAS_TEXTO."
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    con.execute("SELECT * FROM marts.panel_12m").df().to_csv(destino, index=False)
    return destino


def leer_base(ruta: Path | None = None) -> pd.DataFrame:
    """Lee la base final con los mismos tipos que tiene en el almacén."""
    datos = pd.read_csv(ruta or ruta_base_modelo(), dtype={c: "string" for c in COLUMNAS_TEXTO})
    for columna in COLUMNAS_TEXTO:
        datos[columna] = datos[columna].astype(object).where(datos[columna].notna(), None)
    return datos


def main() -> int:
    origen = ruta_almacen()
    if not origen.is_file():
        print(f"No existe el almacén {origen}. Ejecuta `python -m radar.pipeline`.")
        return 1
    con = duckdb.connect(str(origen), read_only=True)
    destino = exportar_base(con)
    filas = con.execute("SELECT count(*) FROM marts.panel_12m").fetchone()[0]
    con.close()
    print(f"Base final del modelo: {destino}")
    print(f"  {filas:,} personas, {destino.stat().st_size / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
