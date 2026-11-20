"""Series del BCRP (BCRPData).

La API acepta hasta 10 series por consulta y devuelve los valores como texto.
Aquí solo se descarga y se aplana la respuesta; el tipado se hace en SQL (staging).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from radar.ingesta.descarga import descargar

URL_API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
MAX_SERIES_POR_CONSULTA = 10

# Códigos verificados contra la API el 2026-11-15.
GRUPOS: dict[str, dict] = {
    # 26 entidades (24 departamentos, Callao y Total) x 3 monedas.
    "credito_departamento": {
        "codigos": [f"RD{n}DM" for n in range(13560, 13638)],
        "inicio": "2004-1",
    },
    # Puestos de trabajo, ingreso promedio y masa salarial del sector formal.
    "empleo_formal": {
        "codigos": [f"PN{n}GM" for n in range(31879, 31887)],
        "inicio": "2015-1",
    },
}

COLUMNAS = ["grupo", "codigo", "nombre_serie", "periodo", "valor_texto"]


def lotes(codigos: list[str], tamanio: int = MAX_SERIES_POR_CONSULTA) -> list[list[str]]:
    return [codigos[i : i + tamanio] for i in range(0, len(codigos), tamanio)]


def url_consulta(codigos: list[str], inicio: str, fin: str) -> str:
    return f"{URL_API}/{'-'.join(codigos)}/json/{inicio}/{fin}/esp"


def ruta_lote(dir_raw: Path, grupo: str, indice: int) -> Path:
    return dir_raw / "bcrp" / f"{grupo}_{indice:02d}.json"


def descargar_grupo(grupo: str, dir_raw: Path, fin: str | None = None) -> dict[str, dict]:
    """Descarga todas las series de un grupo. Devuelve la procedencia por archivo."""
    definicion = GRUPOS[grupo]
    fin = fin or f"{date.today().year}-12"
    procedencia = {}
    for indice, codigos in enumerate(lotes(definicion["codigos"])):
        destino = ruta_lote(dir_raw, grupo, indice)
        entrada = descargar(url_consulta(codigos, definicion["inicio"], fin), destino)
        procedencia[destino.relative_to(dir_raw).as_posix()] = entrada
    return procedencia


def parsear_respuesta(grupo: str, codigos: list[str], contenido: dict) -> list[tuple]:
    """Aplana una respuesta de la API a filas (grupo, código, nombre, periodo, valor).

    La API no devuelve los códigos: las series vienen en el orden en que se pidieron.
    """
    series = contenido["config"]["series"]
    if len(series) != len(codigos):
        raise ValueError(
            f"Se pidieron {len(codigos)} series y la API devolvió {len(series)}: {codigos}"
        )
    filas = []
    for periodo in contenido["periods"]:
        valores = periodo["values"]
        if len(valores) != len(codigos):
            raise ValueError(f"Periodo {periodo['name']} con {len(valores)} valores")
        for codigo, serie, valor in zip(codigos, series, valores, strict=True):
            filas.append((grupo, codigo, serie["name"], periodo["name"], valor))
    return filas


def leer_grupo(grupo: str, dir_raw: Path) -> list[tuple]:
    """Lee los JSON ya descargados de un grupo."""
    filas = []
    for indice, codigos in enumerate(lotes(GRUPOS[grupo]["codigos"])):
        ruta = ruta_lote(dir_raw, grupo, indice)
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        filas.extend(parsear_respuesta(grupo, codigos, contenido))
    return filas
