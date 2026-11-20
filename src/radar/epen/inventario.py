"""Inventario de los .dta de la EPEN contra el esquema verificado.

Uso:
    python -m radar.epen.inventario

Lee solo los metadatos de cada archivo y la columna del año. No modifica nada.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pyreadstat

from radar.config import VAR_ENTORNO_EPEN, dir_epen
from radar.epen.esquema import ANIOS_ESPERADOS, VARIABLES_STAGING


@dataclass
class InformeArchivo:
    archivo: str
    filas: int
    n_variables: int
    filas_por_anio: dict[int, int] = field(default_factory=dict)
    faltantes: list[str] = field(default_factory=list)
    # nombre esperado -> nombre encontrado, cuando solo cambian mayúsculas y minúsculas
    distinta_caja: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.faltantes


def inspeccionar(ruta: Path) -> InformeArchivo:
    """Compara las variables de un .dta con las que necesita el almacén."""
    _, meta = pyreadstat.read_dta(str(ruta), metadataonly=True)
    columnas = list(meta.column_names)
    por_minuscula = {c.lower(): c for c in columnas}

    faltantes: list[str] = []
    distinta_caja: dict[str, str] = {}
    for variable in VARIABLES_STAGING:
        encontrada = por_minuscula.get(variable.lower())
        if encontrada is None:
            faltantes.append(variable)
        elif encontrada != variable:
            distinta_caja[variable] = encontrada

    filas_por_anio: dict[int, int] = {}
    filas = meta.number_rows
    col_anio = por_minuscula.get("anio")
    if col_anio is not None:
        df, _ = pyreadstat.read_dta(str(ruta), usecols=[col_anio])
        anios = pd.to_numeric(df[col_anio], errors="coerce").dropna().astype(int)
        filas_por_anio = {int(a): int(n) for a, n in anios.value_counts().sort_index().items()}
        if filas is None:
            filas = len(df)

    return InformeArchivo(
        archivo=ruta.name,
        filas=int(filas or 0),
        n_variables=len(columnas),
        filas_por_anio=filas_por_anio,
        faltantes=faltantes,
        distinta_caja=distinta_caja,
    )


def inventariar(carpeta: Path) -> list[InformeArchivo]:
    """Inspecciona todos los .dta de la carpeta, en orden alfabético."""
    rutas = sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".dta")
    return [inspeccionar(ruta) for ruta in rutas]


def anios_faltantes(informes: list[InformeArchivo]) -> list[int]:
    cubiertos = {anio for informe in informes for anio in informe.filas_por_anio}
    return [anio for anio in ANIOS_ESPERADOS if anio not in cubiertos]


def main() -> int:
    carpeta = dir_epen()
    if not carpeta.is_dir():
        print(f"No existe la carpeta de EPEN: {carpeta}")
        print(f"Crea la carpeta y copia los .dta, o define {VAR_ENTORNO_EPEN}.")
        return 1

    informes = inventariar(carpeta)
    if not informes:
        print(f"La carpeta {carpeta} no contiene archivos .dta.")
        return 1

    print(f"Carpeta: {carpeta}")
    for informe in informes:
        print(f"\n{informe.archivo}")
        print(f"  filas: {informe.filas:,}  variables: {informe.n_variables}")
        print(f"  filas por año: {informe.filas_por_anio or 'sin variable ANIO'}")
        if informe.distinta_caja:
            print(f"  mismo nombre con otra caja: {informe.distinta_caja}")
        if informe.faltantes:
            print(f"  FALTAN variables que usa el almacén: {informe.faltantes}")
        else:
            print("  variables que usa el almacén: completas")

    sin_cubrir = anios_faltantes(informes)
    if sin_cubrir:
        print(f"\nAños sin cubrir: {sin_cubrir}")

    todo_bien = all(informe.ok for informe in informes) and not sin_cubrir
    print("\nResultado:", "OK" if todo_bien else "hay diferencias por revisar")
    return 0 if todo_bien else 1


if __name__ == "__main__":
    sys.exit(main())
