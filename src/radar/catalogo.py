"""Valores válidos para consultar los productos publicados: años, departamentos e indicadores.

Lo comparten la API y la aplicación web.
"""

from __future__ import annotations

from typing import Literal

ANIOS = (2022, 2023, 2024, 2025)

Indicador = Literal[
    "ocupados",
    "tasa_informalidad",
    "tasa_afiliacion_pension",
    "tasa_subempleo_horas",
    "ingreso_promedio",
    "ingreso_mediano",
    "score_vulnerabilidad",
]

# Los 24 departamentos de la EPEN. El Callao (07) va dentro de Lima (15).
DEPARTAMENTOS: dict[str, str] = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
    "06": "Cajamarca", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco", "11": "Ica",
    "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto",
    "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura", "21": "Puno",
    "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali",
}  # fmt: skip

INDICADORES: dict[str, dict[str, str]] = {
    "ocupados": {"nombre": "población ocupada", "unidad": "personas"},
    "tasa_informalidad": {"nombre": "tasa de empleo informal", "unidad": "porcentaje"},
    "tasa_afiliacion_pension": {
        "nombre": "tasa de afiliación a un sistema de pensiones",
        "unidad": "porcentaje",
    },
    "tasa_subempleo_horas": {"nombre": "tasa de subempleo por horas", "unidad": "porcentaje"},
    "ingreso_promedio": {"nombre": "ingreso mensual promedio por trabajo", "unidad": "soles"},
    "ingreso_mediano": {"nombre": "ingreso mensual mediano por trabajo", "unidad": "soles"},
    "score_vulnerabilidad": {
        "nombre": "probabilidad estimada de perder ingreso laboral en 12 meses",
        "unidad": "porcentaje",
    },
}
