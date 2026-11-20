"""Carga la serie trimestral sobre la que se entrena y evalúa el nowcast."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from radar.config import ruta_almacen


def cargar_serie(ruta_db: Path | None = None, solo_con_epen: bool = True) -> pd.DataFrame:
    """Serie nacional trimestral de `marts.nowcast_trimestral`, ordenada e indexada por fecha.

    Con `solo_con_epen` devuelve los trimestres que tienen empleo de la EPEN y los tres
    meses del BCRP: son los que sirven para entrenar y evaluar. Sin él devuelve todos,
    incluidos los que solo tienen indicadores del BCRP (antes de 2022 y los más recientes).
    """
    filtro = "WHERE ocupados_miles IS NOT NULL AND meses_bcrp = 3" if solo_con_epen else ""
    con = duckdb.connect(str(ruta_db or ruta_almacen()), read_only=True)
    try:
        serie = con.execute(f"SELECT * FROM marts.nowcast_trimestral {filtro} ORDER BY fecha").df()
    finally:
        con.close()
    return serie.set_index("fecha")
