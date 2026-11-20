"""Variables del modelo, preparación de la matriz y partición temporal.

Todo predictor es una característica de la persona en la visita de origen. Las columnas
del destino (12 meses después) solo definen el evento y aquí se rechazan como predictor.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

OBJETIVO_PRINCIPAL = "pierde_ingreso_30"
OBJETIVO_CONTRASTE = "pierde_empleo"
OBJETIVOS = (OBJETIVO_PRINCIPAL, "pierde_ingreso_50", OBJETIVO_CONTRASTE)

NUMERICAS = ["edad", "log_ingreso", "horas_semana", "log_trabajadores"]
BOOLEANAS = ["informal", "afiliado_pension", "quiere_mas_horas", "busca_otro_trabajo"]
CATEGORICAS = [
    "nivel_educativo",
    "ccdd",
    "area_nombre",
    "ciiu_seccion",
    "ocupacion_gran_grupo",
    "categoria_ocupacional",
    "tipo_empleador",
    "registro_sunat",
    "tamanio_empresa",
    "frecuencia_pago",
    "seguro_salud",
    "trimestre",
]
PREDICTORES = NUMERICAS + BOOLEANAS + CATEGORICAS

# Variables que la base trae y el modelo no usa. El sexo se conserva solo para auditar
# si el modelo trata distinto a hombres y mujeres. Lengua materna y autoidentificación
# étnica ni siquiera llegan a la base de modelado.
EXCLUIDAS_POR_SENSIBLES = ["sexo"]


def preparar(datos: pd.DataFrame) -> pd.DataFrame:
    """Matriz de predictores a partir de filas con las columnas del origen.

    Sirve igual para la base de modelado y para puntuar a los ocupados de un año: usa
    solo columnas que existen en la visita de origen.
    """
    x = pd.DataFrame(index=datos.index)
    x["edad"] = datos["edad"].astype(float)
    x["log_ingreso"] = np.log1p(datos["ingreso_total"].astype(float))
    x["horas_semana"] = datos["horas_semana"].astype(float)
    x["log_trabajadores"] = np.log1p(datos["trabajadores_empresa"].astype(float))
    for columna in BOOLEANAS:
        x[columna] = datos[columna].fillna(False).astype(bool).astype(float)
    for columna in CATEGORICAS:
        valores = datos[columna]
        if pd.api.types.is_numeric_dtype(valores):
            valores = valores.astype("Int64")
        x[columna] = valores.astype("string").fillna("(sin dato)").astype(object)
    return x[PREDICTORES]


@dataclass(frozen=True)
class Particion:
    """Filas de entrenamiento, validación y prueba, por año de la visita de origen."""

    entrenamiento: pd.DataFrame
    validacion: pd.DataFrame
    prueba: pd.DataFrame

    @property
    def anios(self) -> dict[str, list[int]]:
        return {
            nombre: sorted(int(a) for a in parte["anio_origen"].unique())
            for nombre, parte in (
                ("entrenamiento", self.entrenamiento),
                ("validacion", self.validacion),
                ("prueba", self.prueba),
            )
        }


def partir_por_cohorte(panel: pd.DataFrame) -> Particion:
    """Partición temporal: el último año de origen es la prueba y el anterior, la validación.

    Lo que el modelo ve al entrenar ocurrió antes que aquello con lo que se evalúa, igual
    que cuando se use. Como la base tiene una fila por persona, nadie queda en dos partes.
    """
    anios = sorted(panel["anio_origen"].unique())
    if len(anios) < 3:
        raise ValueError(f"Se necesitan al menos 3 años de origen y hay {len(anios)}")
    if panel["llave_panel"].duplicated().any():
        raise ValueError("La base de modelado debe tener una sola fila por persona")
    return Particion(
        entrenamiento=panel[panel["anio_origen"] < anios[-2]],
        validacion=panel[panel["anio_origen"] == anios[-2]],
        prueba=panel[panel["anio_origen"] == anios[-1]],
    )
