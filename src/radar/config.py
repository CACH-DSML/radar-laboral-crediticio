"""Rutas del proyecto. Los datos viven fuera del control de versiones."""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

VAR_ENTORNO_EPEN = "RADAR_EPEN_DIR"
VAR_ENTORNO_DATOS = "RADAR_DATA_DIR"
VAR_ENTORNO_DUCKDB = "RADAR_DUCKDB"


def dir_epen() -> Path:
    """Carpeta con los .dta anuales de la EPEN.

    Por defecto es la carpeta `EPEN` junto al repositorio. Se cambia con la variable
    de entorno RADAR_EPEN_DIR.
    """
    personalizada = os.environ.get(VAR_ENTORNO_EPEN)
    if personalizada:
        return Path(personalizada)
    return RAIZ.parent / "EPEN"


def dir_datos() -> Path:
    """Carpeta de datos del proyecto (`data/`, ignorada por git)."""
    personalizada = os.environ.get(VAR_ENTORNO_DATOS)
    if personalizada:
        return Path(personalizada)
    return RAIZ / "data"


def dir_raw() -> Path:
    """Archivos tal como los entrega cada fuente."""
    return dir_datos() / "raw"


def ruta_duckdb() -> Path:
    """Almacén que leen la API y la aplicación.

    Por defecto es `radar.duckdb` dentro de la carpeta de datos. RADAR_DUCKDB apunta a
    otro archivo, por ejemplo la base del dashboard `dashboard/radar_demo.duckdb`, que solo tiene
    las tablas agregadas que usan la API y la aplicación.
    """
    personalizada = os.environ.get(VAR_ENTORNO_DUCKDB)
    if personalizada:
        return Path(personalizada)
    return ruta_almacen()


def ruta_almacen() -> Path:
    """Almacén completo que construye `python -m radar.pipeline`. No cambia con RADAR_DUCKDB,
    para que el pipeline nunca escriba sobre la base de demo."""
    return dir_datos() / "radar.duckdb"


def ruta_base_modelo() -> Path:
    """Base final del modelo en CSV (`python -m radar.modelo.base`). Siempre en la carpeta
    `data/` del repositorio, que no se sube: son microdatos de personas."""
    return RAIZ / "data" / "base_modelo.csv"
