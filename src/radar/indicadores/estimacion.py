"""Estimación con diseño muestral complejo.

Los resultados se compararon con 1 120 estimaciones de `svy` en Stata.

Convenciones comunes a todas las funciones:

- `datos` trae **toda** la muestra del diseño (por ejemplo, toda la PET de un año con
  factor), no solo las filas del grupo de interés.
- `dominio` es una serie booleana alineada con `datos` que marca el grupo de interés.
  El grupo se estima como dominio: las filas fuera de él aportan cero, pero sus
  conglomerados siguen contando para la varianza. Filtrar las filas antes de estimar da
  el mismo valor y un error estándar distinto.
- La varianza se calcula por linealización de Taylor, con conglomerados dentro de
  estratos y sin corrección por población finita. Es lo que hace `svy` en Stata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

UpmUnica = Literal["error", "certeza"]


@dataclass(frozen=True)
class Diseno:
    """Describe el diseño muestral con nombres de columnas de `datos`.

    `estratos` admite una o varias columnas; con varias, el estrato es su cruce.
    `upm_unica` dice qué hacer con un estrato que tiene un solo conglomerado:
    "error" detiene la estimación; "certeza" lo trata como unidad de certeza, que no
    aporta varianza (equivale a `singleunit(certainty)` en Stata).
    """

    peso: str = "factor"
    upm: str = "conglomerado"
    estratos: tuple[str, ...] = ("estrato",)
    upm_unica: UpmUnica = "error"


@dataclass(frozen=True)
class Estimacion:
    """Resultado de una estimación.

    valor:  estimación puntual.
    ee:     error estándar; `nan` si el estimador no lo calcula.
    n:      filas del dominio, sin expandir.
    n_upm:  conglomerados con al menos una fila del dominio.
    """

    valor: float
    ee: float
    n: int
    n_upm: int

    @property
    def cv(self) -> float:
        """Coeficiente de variación, como proporción. `nan` si no se puede calcular."""
        if math.isnan(self.ee) or self.valor == 0:
            return math.nan
        return self.ee / abs(self.valor)


# --- Piezas internas ------------------------------------------------------------------


@dataclass(frozen=True)
class _Muestra:
    """La muestra ya preparada para estimar.

    peso:           factor de expansión de cada fila.
    en_dominio:     verdadero en las filas del grupo de interés.
    upm:            número de conglomerado de cada fila (0, 1, 2, ...).
    estrato_de_upm: número de estrato de cada conglomerado.
    """

    peso: np.ndarray
    en_dominio: np.ndarray
    upm: np.ndarray
    estrato_de_upm: np.ndarray

    @property
    def n(self) -> int:
        return int(self.en_dominio.sum())

    @property
    def n_upm(self) -> int:
        return int(np.unique(self.upm[self.en_dominio]).size)


def _preparar(datos: pd.DataFrame, diseno: Diseno, dominio: pd.Series | None) -> _Muestra:
    """Valida el diseño y numera conglomerados y estratos."""
    columnas_diseno = [diseno.peso, diseno.upm, *diseno.estratos]
    con_nulos = [c for c in columnas_diseno if datos[c].isna().any()]
    if con_nulos:
        raise ValueError(f"Hay valores nulos en las columnas del diseño: {con_nulos}")

    if dominio is None:
        en_dominio = np.ones(len(datos), dtype=bool)
    else:
        if len(dominio) != len(datos):
            raise ValueError("El dominio debe tener una fila por cada fila de los datos")
        en_dominio = np.asarray(dominio, dtype=bool)
    if not en_dominio.any():
        raise ValueError("El dominio está vacío: ninguna fila cumple la condición")

    # Un conglomerado se identifica dentro de su estrato: el mismo código en dos
    # estratos distintos son dos conglomerados distintos.
    estratos = list(diseno.estratos)
    estrato = datos.groupby(estratos, sort=False).ngroup().to_numpy()
    upm = datos.groupby([*estratos, diseno.upm], sort=False).ngroup().to_numpy()
    estrato_de_upm = np.empty(upm.max() + 1, dtype=np.int64)
    estrato_de_upm[upm] = estrato

    return _Muestra(
        peso=datos[diseno.peso].to_numpy(dtype=float),
        en_dominio=en_dominio,
        upm=upm,
        estrato_de_upm=estrato_de_upm,
    )


def _valores(datos: pd.DataFrame, columna: str, muestra: _Muestra) -> np.ndarray:
    """Valores de una columna, con cero fuera del dominio.

    Un nulo fuera del dominio no importa (el ingreso de quien no trabaja). Dentro del
    dominio es un error: no se puede promediar un dato que falta sin decidir qué hacer.
    """
    valores = datos[columna].to_numpy(dtype=float)
    if np.isnan(valores[muestra.en_dominio]).any():
        raise ValueError(f"La columna '{columna}' tiene un valor nulo dentro del dominio")
    return np.where(muestra.en_dominio, valores, 0.0)


def _error_estandar_de_total(z: np.ndarray, muestra: _Muestra, diseno: Diseno) -> float:
    """Error estándar del total de `z`, donde `z` ya viene multiplicada por el peso.

    1. Suma `z` por conglomerado.
    2. En cada estrato con `n` conglomerados, mide cuánto se alejan esos totales de su
       promedio: suma de cuadrados por `n / (n - 1)`.
    3. Suma los estratos y saca la raíz.
    """
    total_por_upm = np.bincount(muestra.upm, weights=z)

    estrato = muestra.estrato_de_upm
    upm_por_estrato = np.bincount(estrato)
    if (upm_por_estrato == 1).any() and diseno.upm_unica == "error":
        raise ValueError(
            f"Hay {int((upm_por_estrato == 1).sum())} estrato(s) con un solo conglomerado: "
            "no se puede medir la variación dentro de ellos. Une estratos o usa "
            "upm_unica='certeza'."
        )

    promedio_del_estrato = np.bincount(estrato, weights=total_por_upm) / upm_por_estrato
    desvio = total_por_upm - promedio_del_estrato[estrato]
    suma_de_cuadrados = np.bincount(estrato, weights=desvio**2)

    # Un estrato con un solo conglomerado tiene desvío cero: como certeza no aporta nada.
    varios = upm_por_estrato > 1
    correccion = upm_por_estrato[varios] / (upm_por_estrato[varios] - 1)
    varianza = float((correccion * suma_de_cuadrados[varios]).sum())
    return math.sqrt(varianza)


def _razon(
    numerador: np.ndarray, denominador: np.ndarray, muestra: _Muestra, diseno: Diseno
) -> Estimacion:
    """Razón entre los totales expandidos de dos variables ya recortadas al dominio."""
    total_numerador = float((muestra.peso * numerador).sum())
    total_denominador = float((muestra.peso * denominador).sum())
    if total_denominador == 0:
        raise ValueError("El total del denominador es cero: la razón no está definida")
    razon = total_numerador / total_denominador

    # Linealización de Taylor: la razón se aproxima por el total de esta variable `z`.
    # `numerador - razon * denominador` es lo que cada persona se aparta de la razón.
    z = muestra.peso * (numerador - razon * denominador) / total_denominador
    return Estimacion(
        valor=razon,
        ee=_error_estandar_de_total(z, muestra, diseno),
        n=muestra.n,
        n_upm=muestra.n_upm,
    )


def _mediana_ponderada(valores: np.ndarray, pesos: np.ndarray) -> float:
    """Menor valor cuyo peso acumulado alcanza la mitad del peso total."""
    orden = np.argsort(valores, kind="stable")
    valores, pesos = valores[orden], pesos[orden]
    acumulado = np.cumsum(pesos)
    mitad = acumulado[-1] / 2
    posicion = int(np.searchsorted(acumulado, mitad, side="left"))
    if acumulado[posicion] == mitad and posicion + 1 < len(valores):
        return float((valores[posicion] + valores[posicion + 1]) / 2)
    return float(valores[posicion])


def _error_estandar_por_grupo(
    z: np.ndarray, grupo: np.ndarray, n_grupos: int, muestra: _Muestra, diseno: Diseno
) -> np.ndarray:
    """Lo mismo que `_error_estandar_de_total`, para muchos grupos a la vez.

    `z` trae, para cada fila, su aporte al total de su propio grupo. `grupo` vale -1 en
    las filas que no pertenecen a ningún grupo: aportan cero a todos.

    Un conglomerado sin filas de un grupo tiene total cero para ese grupo, y aun así
    cuenta. Por eso no se recorren todos los cruces de grupo y conglomerado, sino solo
    los que tienen filas, usando que para `n` totales `t` de un estrato:
        suma de (t - promedio)^2 = suma de t^2 - (suma de t)^2 / n
    donde `n` es el número de conglomerados del estrato, tengan o no filas del grupo.
    """
    upm_por_estrato = np.bincount(muestra.estrato_de_upm)
    if (upm_por_estrato == 1).any() and diseno.upm_unica == "error":
        raise ValueError(
            f"Hay {int((upm_por_estrato == 1).sum())} estrato(s) con un solo conglomerado: "
            "no se puede medir la variación dentro de ellos. Une estratos o usa "
            "upm_unica='certeza'."
        )
    n_upm, n_estratos = len(muestra.estrato_de_upm), len(upm_por_estrato)

    # Total de z por cada par (grupo, conglomerado) que tiene filas.
    con_grupo = grupo >= 0
    par = grupo[con_grupo].astype(np.int64) * n_upm + muestra.upm[con_grupo]
    pares, indice = np.unique(par, return_inverse=True)
    total_del_par = np.bincount(indice, weights=z[con_grupo])
    grupo_del_par, upm_del_par = pares // n_upm, pares % n_upm

    # Suma y suma de cuadrados de esos totales por cada par (grupo, estrato).
    celda = grupo_del_par * n_estratos + muestra.estrato_de_upm[upm_del_par]
    celdas, indice = np.unique(celda, return_inverse=True)
    suma = np.bincount(indice, weights=total_del_par)
    suma_de_cuadrados = np.bincount(indice, weights=total_del_par**2)
    grupo_de_celda, estrato_de_celda = celdas // n_estratos, celdas % n_estratos

    n = upm_por_estrato[estrato_de_celda].astype(float)
    varios = n > 1
    aporte = np.zeros(len(celdas))
    aporte[varios] = (
        n[varios] / (n[varios] - 1) * (suma_de_cuadrados[varios] - suma[varios] ** 2 / n[varios])
    )
    varianza = np.bincount(grupo_de_celda, weights=aporte, minlength=n_grupos)
    return np.sqrt(np.clip(varianza, 0.0, None))  # el redondeo puede dejar un -1e-12


# --- Estimadores ----------------------------------------------------------------------


def estimar_total(
    datos: pd.DataFrame, y: str, diseno: Diseno, dominio: pd.Series | None = None
) -> Estimacion:
    """Total expandido de `y` en el dominio, con su error estándar."""
    muestra = _preparar(datos, diseno, dominio)
    z = muestra.peso * _valores(datos, y, muestra)
    return Estimacion(
        valor=float(z.sum()),
        ee=_error_estandar_de_total(z, muestra, diseno),
        n=muestra.n,
        n_upm=muestra.n_upm,
    )


def estimar_razon(
    datos: pd.DataFrame,
    numerador: str,
    denominador: str,
    diseno: Diseno,
    dominio: pd.Series | None = None,
) -> Estimacion:
    """Razón entre dos totales expandidos del dominio, con su error estándar.

    Es el estimador base: una media y una proporción son razones.
    """
    muestra = _preparar(datos, diseno, dominio)
    return _razon(
        _valores(datos, numerador, muestra), _valores(datos, denominador, muestra), muestra, diseno
    )


def estimar_media(
    datos: pd.DataFrame, y: str, diseno: Diseno, dominio: pd.Series | None = None
) -> Estimacion:
    """Media de `y` en el dominio. Las filas con `y` nulo fuera del dominio no estorban.

    Es la razón entre el total de `y` y el total de personas del dominio. El
    denominador vale 1 dentro del dominio y 0 fuera.
    """
    muestra = _preparar(datos, diseno, dominio)
    personas = muestra.en_dominio.astype(float)
    return _razon(_valores(datos, y, muestra), personas, muestra, diseno)


def estimar_proporcion(
    datos: pd.DataFrame, condicion: str, diseno: Diseno, dominio: pd.Series | None = None
) -> Estimacion:
    """Proporción del dominio que cumple `condicion` (columna booleana), entre 0 y 1.

    Es la media de una variable que vale 1 si se cumple la condición y 0 si no.
    """
    muestra = _preparar(datos, diseno, dominio)
    if datos[condicion][muestra.en_dominio].isna().any():
        raise ValueError(f"La columna '{condicion}' tiene un valor nulo dentro del dominio")
    cumple = np.where(muestra.en_dominio, datos[condicion].fillna(False).astype(bool), False)
    personas = muestra.en_dominio.astype(float)
    return _razon(cumple.astype(float), personas, muestra, diseno)


def estimar_mediana(
    datos: pd.DataFrame, y: str, diseno: Diseno, dominio: pd.Series | None = None
) -> Estimacion:
    """Mediana ponderada de `y` en el dominio.

    Valor: el menor `y` cuyo peso acumulado alcanza la mitad del peso del dominio. Si el
    acumulado cae exactamente en la mitad, el promedio de ese valor y el siguiente (así
    lo hace `_pctile` en Stata). No calcula error estándar: devuelve `nan`.
    """
    muestra = _preparar(datos, diseno, dominio)
    _valores(datos, y, muestra)  # solo para rechazar nulos dentro del dominio

    mediana = _mediana_ponderada(
        datos[y].to_numpy(dtype=float)[muestra.en_dominio], muestra.peso[muestra.en_dominio]
    )
    return Estimacion(valor=mediana, ee=math.nan, n=muestra.n, n_upm=muestra.n_upm)


Estadistico = Literal["total", "media", "proporcion", "mediana"]


def estimar_por_grupo(
    datos: pd.DataFrame,
    estadistico: Estadistico,
    y: str,
    por: list[str],
    diseno: Diseno,
    dominio: pd.Series | None = None,
) -> pd.DataFrame:
    """Estima el mismo indicador en cada grupo que definen las columnas `por`.

    Da exactamente lo mismo que llamar a `estimar_total`, `estimar_media`,
    `estimar_proporcion` o `estimar_mediana` una vez por grupo, con el dominio recortado a
    ese grupo, pero en una sola pasada. Sirve para tablas con miles de celdas.

    Devuelve una fila por grupo con al menos una fila del dominio, con las columnas de
    `por` y `valor`, `ee`, `n` y `n_upm`. Con `por` vacío devuelve una sola fila.
    """
    muestra = _preparar(datos, diseno, dominio)
    dentro = muestra.en_dominio

    # Número de grupo de cada fila del dominio; -1 fuera del dominio.
    if por:
        claves = datos.loc[dentro, por]
        if claves.isna().any().any():
            raise ValueError(f"Hay valores nulos en {por} dentro del dominio")
        agrupado = claves.groupby(por, sort=True)
        etiquetas = agrupado.size().index.to_frame(index=False)
        grupo_en_dominio = agrupado.ngroup().to_numpy()
    else:
        etiquetas = pd.DataFrame(index=[0])
        grupo_en_dominio = np.zeros(int(dentro.sum()), dtype=np.int64)
    n_grupos = len(etiquetas)
    grupo = np.full(len(datos), -1, dtype=np.int64)
    grupo[dentro] = grupo_en_dominio

    if estadistico == "proporcion":
        if datos[y][dentro].isna().any():
            raise ValueError(f"La columna '{y}' tiene un valor nulo dentro del dominio")
        valores = np.where(dentro, datos[y].fillna(False).astype(bool), False).astype(float)
    else:
        valores = _valores(datos, y, muestra)
    peso = np.where(dentro, muestra.peso, 0.0)

    if estadistico == "total":
        z = peso * valores
        valor = np.bincount(grupo_en_dominio, weights=z[dentro], minlength=n_grupos)
        ee = _error_estandar_por_grupo(z, grupo, n_grupos, muestra, diseno)
    elif estadistico in ("media", "proporcion"):
        total_y = np.bincount(
            grupo_en_dominio, weights=(peso * valores)[dentro], minlength=n_grupos
        )
        personas = np.bincount(grupo_en_dominio, weights=peso[dentro], minlength=n_grupos)
        if (personas == 0).any():
            raise ValueError("Hay un grupo con peso total cero: su media no está definida")
        valor = total_y / personas
        # La misma linealización de `_razon`, con la razón y el denominador de cada grupo.
        z = np.zeros(len(datos))
        z[dentro] = (
            peso[dentro] * (valores[dentro] - valor[grupo_en_dominio]) / personas[grupo_en_dominio]
        )
        ee = _error_estandar_por_grupo(z, grupo, n_grupos, muestra, diseno)
    elif estadistico == "mediana":
        orden = np.argsort(grupo_en_dominio, kind="stable")
        cortes = np.flatnonzero(np.diff(grupo_en_dominio[orden])) + 1
        valores_por_grupo = np.split(valores[dentro][orden], cortes)
        pesos_por_grupo = np.split(peso[dentro][orden], cortes)
        valor = np.array(
            [
                _mediana_ponderada(v, w)
                for v, w in zip(valores_por_grupo, pesos_por_grupo, strict=True)
            ]
        )
        ee = np.full(n_grupos, math.nan)
    else:
        raise ValueError(f"Estadístico desconocido: {estadistico}")

    n_upm_total = len(muestra.estrato_de_upm)
    pares = np.unique(grupo_en_dominio * n_upm_total + muestra.upm[dentro])
    resultado = etiquetas.reset_index(drop=True)
    resultado["valor"] = valor
    resultado["ee"] = ee
    resultado["n"] = np.bincount(grupo_en_dominio, minlength=n_grupos)
    resultado["n_upm"] = np.bincount(pares // n_upm_total, minlength=n_grupos)
    return resultado
