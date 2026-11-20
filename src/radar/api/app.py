"""API de solo lectura sobre el almacén.

Arranque local:
    uvicorn radar.api.app:app --reload

Cada petición abre el almacén en modo de solo lectura. La API no calcula nada: sirve las
tablas publicadas por `python -m radar.pipeline`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Literal

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query

from radar.catalogo import ANIOS, DEPARTAMENTOS, INDICADORES, Indicador
from radar.config import ruta_duckdb
from radar.modelo.datos import OBJETIVO_CONTRASTE, OBJETIVO_PRINCIPAL

app = FastAPI(
    title="Radar Laboral-Crediticio del Perú",
    description=(
        "Indicadores laborales de la EPEN (INEI) con error estándar, puntaje de "
        "vulnerabilidad del ingreso por segmento y métricas del modelo. No predice impago."
    ),
    version="1.0.0",
)

Desagregacion = Literal[
    "nacional", "departamento", "rama", "seccion", "ocupacion", "departamento_rama",
    "departamento_seccion", "departamento_ocupacion", "departamento_seccion_ocupacion",
]  # fmt: skip


def conexion() -> Iterator[duckdb.DuckDBPyConnection]:
    """Conexión de solo lectura al almacén, cerrada al terminar la petición."""
    ruta = ruta_duckdb()
    if not ruta.is_file():
        raise HTTPException(
            503, "El almacén no está construido. Ejecuta `python -m radar.pipeline`."
        )
    con = duckdb.connect(str(ruta), read_only=True)
    try:
        yield con
    finally:
        con.close()


Con = Annotated[duckdb.DuckDBPyConnection, Depends(conexion)]


def _filas(con: duckdb.DuckDBPyConnection, sql: str, parametros: list) -> list[dict]:
    cursor = con.execute(sql, parametros)
    columnas = [d[0] for d in cursor.description]
    return [dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()]


@app.get("/salud")
def salud(con: Con) -> dict:
    """Comprueba que el almacén responde y dice qué contiene."""
    celdas, anios = con.execute(
        "SELECT count(*), count(DISTINCT anio) FROM marts.indicadores"
    ).fetchone()
    segmentos = con.execute("SELECT count(*) FROM marts.score_segmento").fetchone()[0]
    return {
        "estado": "ok",
        "celdas_de_indicadores": celdas,
        "anios": anios,
        "segmentos_con_puntaje": segmentos,
    }


@app.get("/catalogo")
def catalogo() -> dict:
    """Valores válidos para consultar."""
    return {"anios": list(ANIOS), "departamentos": DEPARTAMENTOS, "indicadores": INDICADORES}


@app.get("/indicadores")
def indicadores(
    con: Con,
    indicador: Indicador,
    anio: Annotated[int, Query(ge=ANIOS[0], le=ANIOS[-1])] = ANIOS[-1],
    desagregacion: Desagregacion = "departamento",
    departamento: Annotated[str | None, Query(pattern=r"^\d{2}$")] = None,
    incluir_suprimidas: bool = False,
) -> dict:
    """Celdas de un indicador, con error estándar, muestra y calidad.

    Las celdas suprimidas no traen valor. Por defecto no se devuelven.
    """
    if indicador == "score_vulnerabilidad":
        raise HTTPException(422, "El puntaje se consulta en /score.")
    if departamento is not None and departamento not in DEPARTAMENTOS:
        raise HTTPException(422, "Departamento desconocido. La EPEN no separa el Callao de Lima.")
    condiciones = ["indicador = ?", "anio = ?", "desagregacion = ?"]
    parametros: list = [indicador, anio, desagregacion]
    if departamento is not None:
        condiciones.append("ccdd = ?")
        parametros.append(departamento)
    if not incluir_suprimidas:
        condiciones.append("calidad <> 'suprimida'")
    filas = _filas(
        con,
        "SELECT ccdd, rama_inei, ciiu_seccion, ocupacion_gran_grupo, valor, ee, cv, n, n_upm, "
        f"calidad FROM marts.indicadores WHERE {' AND '.join(condiciones)} "
        "ORDER BY ccdd, rama_inei, ciiu_seccion, ocupacion_gran_grupo",
        parametros,
    )
    return {
        "indicador": indicador,
        "unidad": INDICADORES[indicador]["unidad"],
        "anio": anio,
        "desagregacion": desagregacion,
        "fuente": f"Encuesta Permanente de Empleo Nacional (EPEN), INEI, {anio}",
        "celdas": filas,
    }


@app.get("/score")
def score(
    con: Con,
    desagregacion: Literal[
        "nacional",
        "departamento",
        "rama",
        "ocupacion",
        "departamento_rama",
        "departamento_ocupacion",
    ] = "departamento_rama",  # fmt: skip
    evento: Literal["perdida_de_ingreso", "perdida_de_empleo"] = "perdida_de_ingreso",
    departamento: Annotated[str | None, Query(pattern=r"^\d{2}$")] = None,
) -> dict:
    """Puntaje de vulnerabilidad por segmento: probabilidad estimada, en porcentaje."""
    objetivo = OBJETIVO_PRINCIPAL if evento == "perdida_de_ingreso" else OBJETIVO_CONTRASTE
    condiciones, parametros = ["objetivo = ?", "desagregacion = ?"], [objetivo, desagregacion]
    if departamento is not None:
        condiciones.append("ccdd = ?")
        parametros.append(departamento)
    filas = _filas(
        con,
        "SELECT anio, ccdd, rama_inei, ocupacion_gran_grupo, score, ee, n, n_upm, calidad "
        f"FROM marts.score_segmento WHERE {' AND '.join(condiciones)} "
        "AND calidad <> 'suprimida' ORDER BY score DESC",
        parametros,
    )
    if not filas:
        raise HTTPException(404, "No hay puntajes publicados para esa consulta.")
    return {
        "evento": evento,
        "definicion": (
            "Probabilidad estimada de dejar de estar ocupado o de perder 30% o más del "
            "ingreso laboral en 12 meses."
            if evento == "perdida_de_ingreso"
            else "Probabilidad estimada de dejar de estar ocupado en 12 meses."
        ),
        "advertencia": "No es una probabilidad de impago ni sirve para calificar personas.",
        "desagregacion": desagregacion,
        "segmentos": filas,
    }


@app.get("/modelo")
def modelo(con: Con) -> dict:
    """Métricas del modelo en la cohorte de prueba, y su auditoría por sexo."""
    return {
        "metricas": _filas(
            con,
            "SELECT objetivo, modelo, n, tasa_observada, auc, ks, brier, error_calibracion "
            "FROM marts.modelo_metricas WHERE parte = 'prueba' ORDER BY objetivo, modelo",
            [],
        ),
        "auditoria_por_sexo": _filas(
            con,
            "SELECT objetivo, grupo, n, observado, estimado FROM marts.modelo_auditoria "
            "ORDER BY objetivo, grupo",
            [],
        ),
    }
