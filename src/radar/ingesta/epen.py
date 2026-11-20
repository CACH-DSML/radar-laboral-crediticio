"""Lleva los .dta de la EPEN a la capa cruda.

Los .dta no se descargan: se leen de la carpeta EPEN (ver `radar.config.dir_epen`). Cada
archivo se convierte una sola vez a Parquet, sin tocar nombres ni valores, y sus etiquetas
de variable y de valor se guardan aparte. Si el .dta no cambió, la conversión se omite.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pyreadstat

COLUMNAS_VARIABLES = ["anio", "variable", "etiqueta", "formato"]
COLUMNAS_ETIQUETAS = ["anio", "variable", "codigo", "etiqueta"]
NOMBRE_MANIFIESTO = "manifiesto.json"


def dir_raw_epen(dir_raw: Path) -> Path:
    return dir_raw / "epen"


def ruta_parquet(dir_raw: Path, anio: int) -> Path:
    return dir_raw_epen(dir_raw) / f"epen_{anio}.parquet"


def ruta_metadatos(dir_raw: Path, anio: int) -> Path:
    return dir_raw_epen(dir_raw) / f"epen_{anio}_metadatos.json"


def archivos_dta(carpeta: Path) -> list[Path]:
    return sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".dta")


def _huella(ruta: Path) -> dict:
    estado = ruta.stat()
    return {"bytes": estado.st_size, "modificado_ns": estado.st_mtime_ns}


def _sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def anio_unico(datos: pd.DataFrame, archivo: str) -> int:
    """Devuelve el año de la base. Falla si falta la variable o si mezcla años."""
    columna = next((c for c in datos.columns if c.lower() == "anio"), None)
    if columna is None:
        raise ValueError(f"{archivo}: no tiene la variable ANIO")
    anios = pd.to_numeric(datos[columna], errors="coerce").dropna().astype(int).unique()
    if len(anios) != 1:
        raise ValueError(f"{archivo}: se esperaba un solo año y trae {sorted(anios)}")
    return int(anios[0])


def metadatos(meta, anio: int) -> dict:
    """Etiquetas de variable y de valor, tal como vienen en el .dta."""
    return {
        "anio": anio,
        "variables": [
            {
                "variable": nombre,
                "etiqueta": meta.column_names_to_labels.get(nombre),
                "formato": meta.original_variable_types.get(nombre),
            }
            for nombre in meta.column_names
        ],
        "etiquetas": [
            {"variable": variable, "codigo": float(codigo), "etiqueta": etiqueta}
            for variable, valores in meta.variable_value_labels.items()
            for codigo, etiqueta in valores.items()
        ],
    }


def convertir(ruta_dta: Path, dir_raw: Path) -> dict:
    """Convierte un .dta a Parquet y guarda sus metadatos. Devuelve su procedencia."""
    datos, meta = pyreadstat.read_dta(str(ruta_dta))
    anio = anio_unico(datos, ruta_dta.name)

    destino = ruta_parquet(dir_raw, anio)
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.register("_base", datos)
    con.execute(
        f"COPY (SELECT * FROM _base) TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    con.close()

    ruta_metadatos(dir_raw, anio).write_text(
        json.dumps(metadatos(meta, anio), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return {
        "archivo": ruta_dta.name,
        "anio": anio,
        "filas": len(datos),
        "columnas": datos.shape[1],
        "sha256": _sha256(ruta_dta),
        "convertido_en": datetime.now(UTC).isoformat(timespec="seconds"),
        **_huella(ruta_dta),
    }


def preparar(carpeta_epen: Path, dir_raw: Path, avisar=print) -> dict[int, Path]:
    """Deja un Parquet por año en `dir_raw/epen`. Devuelve año -> ruta del Parquet.

    Reutiliza la conversión anterior si el .dta conserva tamaño y fecha de modificación.
    Falla si dos archivos corresponden al mismo año.
    """
    destino = dir_raw_epen(dir_raw)
    destino.mkdir(parents=True, exist_ok=True)
    ruta_manifiesto = destino / NOMBRE_MANIFIESTO
    previo = (
        json.loads(ruta_manifiesto.read_text(encoding="utf-8")) if ruta_manifiesto.exists() else {}
    )

    manifiesto: dict[str, dict] = {}
    for ruta in archivos_dta(carpeta_epen):
        entrada = previo.get(ruta.name)
        vigente = (
            entrada is not None
            and all(entrada.get(k) == v for k, v in _huella(ruta).items())
            and ruta_parquet(dir_raw, entrada["anio"]).exists()
            and ruta_metadatos(dir_raw, entrada["anio"]).exists()
        )
        if vigente:
            avisar(f"  {ruta.name}: sin cambios, se reutiliza la conversión")
        else:
            avisar(f"  {ruta.name}: convirtiendo a Parquet")
            entrada = convertir(ruta, dir_raw)
        manifiesto[ruta.name] = entrada

    por_anio: dict[int, str] = {}
    for archivo, entrada in manifiesto.items():
        if entrada["anio"] in por_anio:
            raise ValueError(
                f"Dos archivos para el año {entrada['anio']}: "
                f"{por_anio[entrada['anio']]} y {archivo}"
            )
        por_anio[entrada["anio"]] = archivo

    ruta_manifiesto.write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {anio: ruta_parquet(dir_raw, anio) for anio in sorted(por_anio)}


def leer_metadatos(dir_raw: Path, anios: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Une los metadatos de todos los años en dos tablas: variables y etiquetas de valor."""
    variables: list[tuple] = []
    etiquetas: list[tuple] = []
    for anio in anios:
        contenido = json.loads(ruta_metadatos(dir_raw, anio).read_text(encoding="utf-8"))
        variables += [
            (anio, v["variable"], v["etiqueta"], v["formato"]) for v in contenido["variables"]
        ]
        etiquetas += [
            (anio, e["variable"], e["codigo"], e["etiqueta"]) for e in contenido["etiquetas"]
        ]
    return (
        pd.DataFrame(variables, columns=COLUMNAS_VARIABLES),
        pd.DataFrame(etiquetas, columns=COLUMNAS_ETIQUETAS),
    )
