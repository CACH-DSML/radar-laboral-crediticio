"""Cuadros estadísticos de la SBS.

Cuadro B-2349: "Estructura de los Créditos Directos por Departamento y Empresa
Bancaria" (banca múltiple). Cada fila es un banco; cada columna, el porcentaje de sus
créditos directos colocado en un departamento. La última columna es el total en miles
de soles. La SBS asigna el crédito según la oficina que lo colocó.

Se descarga el corte de diciembre de cada año, que es el que se alinea con la EPEN anual.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import openpyxl

from radar.ingesta.descarga import descargar

URL_BASE = "https://intranet2.sbs.gob.pe/estadistica/financiera"
CUADRO_CREDITOS_DEPARTAMENTO = "B-2349"
ANIOS: tuple[int, ...] = (2022, 2023, 2024, 2025)

COLUMNAS = ["fecha_corte", "empresa", "columna", "porcentaje", "total_miles_soles", "archivo"]

# Cuadro B-2401: "Indicadores Financieros por Empresa Bancaria". De ahí sale la
# morosidad de cada banco: créditos atrasados (criterio SBS) sobre créditos directos.
CUADRO_INDICADORES = "B-2401"
FILA_MOROSIDAD = "Créditos Atrasados (criterio SBS)"
COLUMNAS_MOROSIDAD = ["fecha_corte", "empresa", "morosidad_pct", "archivo"]


def url_cuadro(codigo: str, anio: int) -> str:
    """URL del corte de diciembre de un cuadro. Patrón verificado para 2022 a 2025."""
    return f"{URL_BASE}/{anio}/Diciembre/{codigo}-di{anio}.XLS"


def ruta_cuadro(dir_raw: Path, codigo: str, anio: int) -> Path:
    return dir_raw / "sbs" / f"{codigo}-di{anio}.xlsx"


def descargar_creditos_departamento(dir_raw: Path) -> dict[str, dict]:
    procedencia = {}
    for anio in ANIOS:
        destino = ruta_cuadro(dir_raw, CUADRO_CREDITOS_DEPARTAMENTO, anio)
        entrada = descargar(url_cuadro(CUADRO_CREDITOS_DEPARTAMENTO, anio), destino)
        procedencia[destino.relative_to(dir_raw).as_posix()] = entrada
    return procedencia


def descargar_indicadores(dir_raw: Path) -> dict[str, dict]:
    procedencia = {}
    for anio in ANIOS:
        destino = ruta_cuadro(dir_raw, CUADRO_INDICADORES, anio)
        entrada = descargar(url_cuadro(CUADRO_INDICADORES, anio), destino)
        procedencia[destino.relative_to(dir_raw).as_posix()] = entrada
    return procedencia


def _texto(celda) -> str:
    return " ".join(str(celda).split()) if celda is not None else ""


def parsear_creditos_departamento(ruta: Path) -> list[tuple]:
    """Pasa la matriz banco x departamento a filas largas.

    Devuelve (fecha_corte, empresa, columna, porcentaje, total_miles_soles, archivo).
    Conserva la fila "TOTAL BANCA MÚLTIPLE" y la columna de sucursales en el exterior;
    staging decide qué hacer con ellas.
    """
    # La SBS publica el archivo con extensión .XLS pero su contenido es .xlsx.
    libro = openpyxl.load_workbook(io.BytesIO(ruta.read_bytes()), data_only=True)
    filas = list(libro.worksheets[0].iter_rows(values_only=True))

    indice_encabezado = next(
        (i for i, fila in enumerate(filas) if _texto(fila[0]) == "Empresas"), None
    )
    if indice_encabezado is None:
        raise ValueError(f"{ruta.name}: no se encontró la fila de encabezado 'Empresas'")

    fecha_corte = next(
        (fila[0] for fila in filas[:indice_encabezado] if isinstance(fila[0], datetime)), None
    )
    if fecha_corte is None:
        raise ValueError(f"{ruta.name}: no se encontró la fecha de corte")

    encabezado = [_texto(celda) for celda in filas[indice_encabezado]]
    columnas = {i: nombre for i, nombre in enumerate(encabezado) if i > 0 and nombre}
    indice_total = next((i for i, nombre in columnas.items() if nombre.startswith("TOTAL")), None)
    if indice_total is None:
        raise ValueError(f"{ruta.name}: no se encontró la columna de total")

    salida = []
    for fila in filas[indice_encabezado + 1 :]:
        empresa = _texto(fila[0])
        if not empresa:
            continue
        if empresa.startswith(("Fuente", "Nota")):
            break
        for i, nombre in columnas.items():
            if i == indice_total:
                continue
            salida.append(
                (
                    fecha_corte.date().isoformat(),
                    empresa,
                    nombre,
                    fila[i],
                    fila[indice_total],
                    ruta.name,
                )
            )
    if not salida:
        raise ValueError(f"{ruta.name}: no se encontraron filas de empresas")
    return salida


def leer_creditos_departamento(dir_raw: Path) -> list[tuple]:
    filas = []
    for anio in ANIOS:
        filas.extend(
            parsear_creditos_departamento(ruta_cuadro(dir_raw, CUADRO_CREDITOS_DEPARTAMENTO, anio))
        )
    return filas


def parsear_morosidad_por_banco(ruta: Path) -> list[tuple]:
    """Lee la morosidad de cada banco del cuadro de indicadores financieros.

    Devuelve (fecha_corte, empresa, morosidad_pct, archivo). Los bancos están en
    columnas: el encabezado es la primera fila sin texto en la primera celda y con
    nombres en las siguientes; la fecha de corte está arriba, sola en su fila.
    """
    libro = openpyxl.load_workbook(io.BytesIO(ruta.read_bytes()), data_only=True)
    filas = list(libro.worksheets[0].iter_rows(values_only=True))

    fecha = next(
        (fila[0] for fila in filas if fila and isinstance(fila[0], datetime)),
        None,
    )
    if fecha is None:
        raise ValueError(f"{ruta.name}: no se encontró la fecha de corte")
    encabezado = next(
        (
            fila
            for fila in filas
            if fila and fila[0] is None and sum(celda is not None for celda in fila) >= 3
        ),
        None,
    )
    if encabezado is None:
        raise ValueError(f"{ruta.name}: no se encontró el encabezado con los bancos")
    morosidad = next(
        (fila for fila in filas if fila and _texto(fila[0]).startswith(FILA_MOROSIDAD)),
        None,
    )
    if morosidad is None:
        raise ValueError(f"{ruta.name}: no se encontró la fila '{FILA_MOROSIDAD}'")

    return [
        (fecha.date().isoformat(), _texto(banco), float(valor), ruta.name)
        for banco, valor in zip(encabezado[1:], morosidad[1:], strict=False)
        if banco is not None and valor is not None
    ]


def leer_morosidad_por_banco(dir_raw: Path) -> list[tuple]:
    filas: list[tuple] = []
    for anio in ANIOS:
        filas += parsear_morosidad_por_banco(ruta_cuadro(dir_raw, CUADRO_INDICADORES, anio))
    return filas
