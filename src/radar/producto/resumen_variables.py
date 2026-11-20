"""Resumen agregado de las variables del modelo, para el dashboard.

Sale de la cohorte de desarrollo (la que se usó para entrenar), igual que el análisis
univariado del notebook:

- `tramos`: tasa del evento principal por tramo de cada variable que se puede rotular.
  Un tramo con menos de 30 personas queda sin tasa.
- `iv`: Information Value de cada uno de los 20 predictores.
- `correlaciones`: correlación de Spearman entre las variables numéricas y binarias y el
  evento.

Son tablas de pocas filas, sin ninguna persona: lo que va a la base del dashboard.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from radar.catalogo import DEPARTAMENTOS
from radar.modelo import validacion
from radar.modelo.datos import (
    BOOLEANAS,
    NUMERICAS,
    OBJETIVO_PRINCIPAL,
    PREDICTORES,
    partir_por_cohorte,
    preparar,
)

MINIMO_TRAMO = 30
# Mayor valor que registra la EPEN para el número de trabajadores de la empresa.
TOPE_TRABAJADORES = 9998

NOMBRES: dict[str, str] = {
    "edad": "Edad",
    "log_ingreso": "Ingreso mensual",
    "horas_semana": "Horas trabajadas a la semana",
    "log_trabajadores": "Trabajadores en la empresa",
    "informal": "Empleo informal",
    "afiliado_pension": "Afiliado a pensiones",
    "quiere_mas_horas": "Quiere trabajar más horas",
    "busca_otro_trabajo": "Busca otro trabajo",
    "nivel_educativo": "Nivel educativo",
    "ccdd": "Departamento",
    "area_nombre": "Área",
    "ciiu_seccion": "Actividad económica",
    "ocupacion_gran_grupo": "Ocupación",
    "categoria_ocupacional": "Categoría ocupacional",
    "tipo_empleador": "Tipo de empleador",
    "registro_sunat": "Registro en la Sunat",
    "tamanio_empresa": "Tamaño de la empresa",
    "frecuencia_pago": "Frecuencia de pago",
    "seguro_salud": "Seguro de salud",
    "trimestre": "Trimestre de la entrevista",
    OBJETIVO_PRINCIPAL: "Pierde ingreso (evento)",
}

# Grandes grupos de la Clasificación Nacional de Ocupaciones 2015, en nombre corto.
OCUPACIONES: dict[str, str] = {
    "0": "Militares y policías",
    "1": "Directivos",
    "2": "Profesionales",
    "3": "Técnicos",
    "4": "Administrativos",
    "5": "Servicios y ventas",
    "6": "Agricultores calificados",
    "7": "Construcción y oficios",
    "8": "Operadores y conductores",
    "9": "Ocupaciones elementales",
}

# Secciones de la CIIU Revisión 4, en nombre corto.
SECCIONES: dict[str, str] = {
    "A": "Agricultura y pesca", "B": "Minería", "C": "Manufactura", "D": "Electricidad y gas",
    "E": "Agua y residuos", "F": "Construcción", "G": "Comercio", "H": "Transporte",
    "I": "Alojamiento y comidas", "J": "Información y comunicaciones", "K": "Finanzas",
    "L": "Inmobiliarias", "M": "Profesionales y técnicas", "N": "Servicios de apoyo",
    "O": "Administración pública", "P": "Enseñanza", "Q": "Salud", "R": "Arte y recreación",
    "S": "Otros servicios", "T": "Hogares empleadores", "U": "Organismos extraterritoriales",
}  # fmt: skip

# Agrupaciones de los códigos de la EPEN que usan los cuadros del INEI.
NIVELES_EDUCATIVOS: dict[str, str] = {
    **dict.fromkeys(("1", "2", "3", "4", "7"), "Primaria o menos"),
    **dict.fromkeys(("5", "6"), "Secundaria"),
    **dict.fromkeys(("8", "9"), "Superior no universitaria"),
    **dict.fromkeys(("10", "11", "12"), "Universitaria"),
}
CATEGORIAS: dict[str, str] = {
    **dict.fromkeys(("1", "2"), "Independiente o empleador"),
    **dict.fromkeys(("3", "7", "8"), "Dependiente"),
    **dict.fromkeys(("4", "5", "9", "10"), "Familiar no remunerado"),
    "6": "Trabajador del hogar",
}

# Variables que se muestran por tramo, con el rótulo de cada categoría.
CATEGORICAS_ROTULADAS: dict[str, dict[str, str]] = {
    "ccdd": DEPARTAMENTOS,
    "area_nombre": {"Urbana": "Urbana", "Rural": "Rural"},
    "ciiu_seccion": SECCIONES,
    "ocupacion_gran_grupo": OCUPACIONES,
    "nivel_educativo": NIVELES_EDUCATIVOS,
    "categoria_ocupacional": CATEGORIAS,
}
# Orden en que se presentan las categorías agrupadas.
ORDEN_AGRUPADAS = {
    "nivel_educativo": [
        "Primaria o menos", "Secundaria", "Superior no universitaria", "Universitaria",
    ],
    "categoria_ocupacional": [
        "Independiente o empleador", "Dependiente", "Familiar no remunerado",
        "Trabajador del hogar",
    ],
}  # fmt: skip


def _miles(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", " ")


def _rotulos_continuos(variable: str, cortes: np.ndarray) -> list[str]:
    """Rótulo legible de cada intervalo `(a, b]`, en la escala original de la variable."""
    if variable in ("log_ingreso", "log_trabajadores"):
        # Se redondea para que expm1(log1p(3)) = 2,9999... no caiga en el entero anterior.
        cortes = np.round(np.expm1(cortes), 6)
    entero = variable != "log_ingreso"
    prefijo = "S/ " if variable == "log_ingreso" else ""
    rotulos = []
    bordes = [None, *cortes, None]
    for a, b in zip(bordes[:-1], bordes[1:], strict=True):
        if entero:  # valores enteros: (25, 31] es "26 a 31"
            desde = None if a is None else int(np.floor(a)) + 1
            hasta = None if b is None else int(np.floor(b))
            if hasta is not None and hasta >= TOPE_TRABAJADORES:
                hasta = None  # 9998 es el código de "muchos": el tramo queda abierto
            if a is None and hasta == 1 and variable == "log_trabajadores":
                rotulos.append("1 (trabaja solo)")
            elif a is None:
                rotulos.append(f"Hasta {hasta}")
            elif hasta is None:
                rotulos.append(f"{desde} o más")
            else:
                rotulos.append(f"{desde}" if desde == hasta else f"{desde} a {hasta}")
        elif a is None:
            rotulos.append(f"Hasta {prefijo}{_miles(b)}")
        elif b is None:
            rotulos.append(f"Más de {prefijo}{_miles(a)}")
        else:
            rotulos.append(f"{prefijo}{_miles(a)} a {_miles(b)}")
    return rotulos


def _tramos_de(variable: str, valores: pd.Series, y: np.ndarray) -> pd.DataFrame:
    if variable in NUMERICAS:
        tabla = validacion.tabla_woe(valores, y)
        cortes = validacion.cortes_por_cuantil(valores)
        rotulos = _rotulos_continuos(variable, cortes)
        # Mismas etiquetas que pone `validacion.asignar_tramos`; un tramo sin personas no
        # aparece en la tabla, por eso se traduce etiqueta por etiqueta.
        bordes = np.concatenate([[-np.inf], cortes, [np.inf]])
        etiquetas = [
            f"({validacion._fmt(a)}, {validacion._fmt(b)}]"
            for a, b in zip(bordes[:-1], bordes[1:], strict=True)
        ]
        tabla = tabla[tabla["tramo"] != validacion.SIN_DATO].reset_index(drop=True)
        tabla["tramo"] = tabla["tramo"].map(dict(zip(etiquetas, rotulos, strict=True)))
    elif variable in BOOLEANAS:
        tabla = validacion.tabla_woe(valores, y)
        tabla["tramo"] = tabla["tramo"].map({"0.0": "No", "1.0": "Sí"})
    else:
        rotulos = CATEGORICAS_ROTULADAS[variable]
        agrupados = valores.map(rotulos)
        tabla = validacion.tabla_woe(agrupados, y)
        tabla = tabla[tabla["tramo"] != validacion.SIN_DATO]
        if variable in ORDEN_AGRUPADAS:
            orden = ORDEN_AGRUPADAS[variable]
            tabla = tabla.set_index("tramo").reindex(orden).dropna(subset=["n"]).reset_index()
    tabla = tabla.reset_index(drop=True)
    pequenos = tabla["n"] < MINIMO_TRAMO
    return pd.DataFrame(
        {
            "variable": variable,
            "orden": np.arange(1, len(tabla) + 1),
            "tramo": tabla["tramo"].astype(str),
            "n": tabla["n"].astype("int64"),
            "tasa_evento": tabla["tasa_evento"].where(~pequenos),
        }
    )


COLUMNAS = {
    "tramos": ["variable", "orden", "tramo", "n", "tasa_evento"],
    "iv": ["variable", "iv"],
    "correlaciones": ["variable_1", "variable_2", "correlacion"],
}


def resumir(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Tablas `tramos`, `iv` y `correlaciones` de la cohorte de desarrollo.

    Si el panel no alcanza para partirlo en tres cohortes, las tablas quedan vacías.
    """
    try:
        desarrollo = partir_por_cohorte(panel).entrenamiento
    except ValueError:
        return {nombre: pd.DataFrame(columns=columnas) for nombre, columnas in COLUMNAS.items()}
    x = preparar(desarrollo)
    y = desarrollo[OBJETIVO_PRINCIPAL].astype(int).to_numpy()

    iv = pd.DataFrame(
        {
            "variable": PREDICTORES,
            "iv": [validacion.tabla_woe(x[v], y)["iv"].sum() for v in PREDICTORES],
        }
    )
    rotulables = NUMERICAS + BOOLEANAS + list(CATEGORICAS_ROTULADAS)
    tramos = pd.concat([_tramos_de(v, x[v], y) for v in rotulables], ignore_index=True)

    numericas = x[NUMERICAS + BOOLEANAS].assign(**{OBJETIVO_PRINCIPAL: y})
    matriz = numericas.corr(method="spearman")
    correlaciones = (
        matriz.rename_axis("variable_1")
        .reset_index()
        .melt(id_vars="variable_1", var_name="variable_2", value_name="correlacion")
    )
    return {"tramos": tramos, "iv": iv, "correlaciones": correlaciones}
