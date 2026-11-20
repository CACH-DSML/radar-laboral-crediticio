"""Carga desde el almacén la muestra sobre la que se estiman los indicadores."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from radar.config import ruta_almacen

# Columnas de `marts.epen_pet` que usan los indicadores. Los booleanos que solo aplican a
# ocupados llegan como falso para el resto, de modo que sirvan dentro de un dominio.
CONSULTA_PET = """
SELECT
    anio, mes, trimestre, conglomerado, estrato, ccdd, departamento, area_nombre, factor,
    sexo, edad, nivel_educativo, condicion_actividad, ocupado, desocupado, pea,
    coalesce(informal, false) AS informal,
    ocupacion, ocupacion_gran_grupo, ciiu_clase, ciiu_division, ciiu_seccion, rama_inei,
    categoria_ocupacional, tipo_empleador, registro_sunat, tamanio_empresa,
    trabajadores_empresa, frecuencia_pago,
    horas_semana, horas_habituales, coalesce(quiere_mas_horas, false) AS quiere_mas_horas,
    coalesce(busca_otro_trabajo, false) AS busca_otro_trabajo,
    ingreso_total, ingreso_principal, seguro_salud,
    coalesce(afiliado_pension, false) AS afiliado_pension
FROM marts.epen_pet
WHERE tiene_factor AND factor > 0 AND anio = ?
"""


def cargar_pet(
    anio: int, ruta_db: Path | None = None, con: duckdb.DuckDBPyConnection | None = None
) -> pd.DataFrame:
    """PET de un año con factor de expansión: la muestra completa del diseño.

    Deja fuera a las personas sin factor de expansión y a las 21 de
    2023 con factor cero: no representan a nadie y Stata tampoco las cuenta. No filtra
    nada más: los grupos de interés se pasan a los estimadores como dominio.

    Con `con` usa una conexión ya abierta; si no, abre el almacén en modo de solo lectura.
    """
    if con is not None:
        return con.execute(CONSULTA_PET, [anio]).df()
    propia = duckdb.connect(str(ruta_db or ruta_almacen()), read_only=True)
    try:
        return propia.execute(CONSULTA_PET, [anio]).df()
    finally:
        propia.close()
