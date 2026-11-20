"""Esquema de la base anual EPEN que usa el proyecto.

Los nombres se verificaron el 2026-11-15 contra los cuatro .dta anuales (2022 a 2025) y
contra el diccionario de variables de la base anual 2022.
"""

from __future__ import annotations

ANIOS_ESPERADOS: tuple[int, ...] = (2022, 2023, 2024, 2025)

# variable -> para qué la usa el proyecto
VARIABLES_NUCLEO: dict[str, str] = {
    "ANIO": "año de ejecución de la encuesta",
    "MES": "mes de ejecución de la encuesta",
    "CONGLOMERADO": "unidad primaria de muestreo",
    "ESTRATO": "estrato poblacional (8 categorías de tamaño)",
    "CCDD": "departamento (24 códigos; el Callao va dentro de Lima)",
    "LLAVE_PANEL": "llave de la persona en el panel",
    "NROINF": "informante del módulo de empleo (99: sin módulo de empleo)",
    "OCUP300": "condición de actividad",
    "C308_COD": "ocupación principal (Clasificador Nacional de Ocupaciones 2015)",
    "C309_COD": "actividad económica (CIIU Revisión 4, clase)",
    "Informal_P": "situación de informalidad en la ocupación principal",
    "ingtrabw": "ingreso laboral mensual con ingresos extraordinarios",
    "FAC300_ANUAL": "factor de expansión anual de empleo",
}

# Diferencias de nombre entre los .dta. El almacén las absorbe porque une las columnas
# por nombre sin distinguir mayúsculas.
# nombre armonizado -> {año: nombre en la base de ese año}
RENOMBRES_CONOCIDOS: dict[str, dict[int, str]] = {
    "C300n": {2022: "c300n", 2023: "c300n", 2024: "C300n", 2025: "C300n"},
}
# Variables que no están en todos los años.
SOLO_DESDE: dict[str, int] = {"C306A": 2023}

# Variables de la base anual que lee `staging.epen_personas`, con la caja en que las
# publica el INEI. Si una falta en un .dta, la construcción del almacén falla.
VARIABLES_STAGING: tuple[str, ...] = (
    # identificación y diseño muestral
    "ANIO", "MES", "CONGLOMERADO", "MUESTRA", "SELVIV", "HOGAR", "C201", "LLAVE_PANEL",
    "CCDD", "ESTRATO", "AREA", "DIVISION_LIMA", "RESIDENT", "NROINF", "FAC300_ANUAL",
    # características de la persona
    "C203", "C204", "C207", "C208", "C366", "C376", "C377",
    # condición de actividad y ocupación principal
    "OCUP300", "C308_COD", "C309_COD", "C310", "C311", "C312", "C313", "C317", "C317A",
    "Informal_P",
    # horas y subempleo
    "C318_T", "C328_T", "whoraT", "C330", "C331", "C333", "C334", "P209H", "C335", "C338",
    # ingresos
    "I339_1", "I342", "I345_1", "I348", "D341_T", "D344", "D347_T", "D350", "D351_T",
    "INGTOT", "INGTOTP", "ingtrabw",
    # desocupados e inactivos
    "C352", "C353", "C354", "C355", "C356", "C358", "C359",
    # seguro de salud y pensiones
    "SEGURO1", "C364_1", "C364_2", "C364_3", "C364_4",
)  # fmt: skip
# De las anteriores, las que el .dta trae como texto.
VARIABLES_TEXTO: frozenset[str] = frozenset(
    {"MES", "CONGLOMERADO", "SELVIV", "LLAVE_PANEL", "CCDD"}
)
