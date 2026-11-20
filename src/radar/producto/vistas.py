"""Datos y gráficos del dashboard.

Las funciones de datos leen la base del dashboard y devuelven DataFrames; las de gráficos
devuelven gráficos de Altair. `dashboard/app.py` solo las ordena en pantalla: aquí está
lo que se prueba.

Color: un solo tono (azul) de claro a oscuro para toda magnitud, así que en cualquier
mapa o mapa de calor "más oscuro" significa "más". La referencia nacional va en gris.
"""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd

from radar.catalogo import DEPARTAMENTOS, INDICADORES
from radar.modelo.datos import OBJETIVO_CONTRASTE, OBJETIVO_PRINCIPAL
from radar.producto.resumen_variables import NOMBRES, OCUPACIONES

RAMPA = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
AZUL = "#2a78d6"
NARANJA = "#eb6834"
GRIS = "#8a8a85"
GRIS_SIN_DATO = "#e1e0d9"
TINTA, TINTA_CLARA = "#0b0b0b", "#ffffff"
# Departamentos pequeños de la costa: el nombre se escribe hacia el mar (a la izquierda
# del punto) o hacia adentro, para que no se encime con el vecino.
ALINEACION_NOMBRES = {"14": "right", "18": "right", "24": "left"}
# Coma decimal en los ejes (Vega-Lite usa punto).
COMA = "replace(datum.label, '.', ',')"

EVENTOS = {
    "Perder ingreso (caída de 30% o más, o quedarse sin trabajo)": OBJETIVO_PRINCIPAL,
    "Quedarse sin trabajo": OBJETIVO_CONTRASTE,
}
RAMAS = ["Agricultura, pesca y minería", "Manufactura", "Construcción", "Comercio", "Servicios"]
INDICADORES_MAPA = {
    datos["nombre"].capitalize(): clave
    for clave, datos in INDICADORES.items()
    if clave not in ("score_vulnerabilidad", "ocupados")
}


# --- formato -----------------------------------------------------------------------


def pct(valor: float, decimales: int = 1) -> str:
    """47.35 -> '47,4%'. Recibe porcentajes (0-100)."""
    if pd.isna(valor):
        return "sin dato"
    return f"{valor:.{decimales}f}%".replace(".", ",")


def numero(valor: float, decimales: int = 0) -> str:
    if pd.isna(valor):
        return "sin dato"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", " ").replace(".", ",")


def formatear(valor: float, unidad: str) -> str:
    if unidad == "porcentaje":
        return pct(valor)
    if unidad == "soles":
        return f"S/ {numero(valor)}"
    return numero(valor)


# --- datos ---------------------------------------------------------------------------


def cargar_geo(ruta: Path) -> list[dict]:
    """Departamentos del Perú (GeoJSON simplificado; Lima incluye al Callao)."""
    return json.loads(Path(ruta).read_text(encoding="utf-8"))["features"]


def score(con: duckdb.DuckDBPyConnection, objetivo: str, desagregacion: str) -> pd.DataFrame:
    """Puntaje (en %) por segmento, sin celdas suprimidas, con nombres legibles."""
    tabla = con.execute(
        "SELECT ccdd, rama_inei AS rama, ocupacion_gran_grupo, score, ee, n, calidad "
        "FROM marts.score_segmento "
        "WHERE objetivo = ? AND desagregacion = ? AND calidad <> 'suprimida'",
        [objetivo, desagregacion],
    ).df()
    tabla["departamento"] = tabla["ccdd"].map(DEPARTAMENTOS)
    tabla["ocupacion"] = tabla["ocupacion_gran_grupo"].map(OCUPACIONES)
    return tabla.sort_values("score", ascending=False, ignore_index=True)


def score_nacional(con: duckdb.DuckDBPyConnection, objetivo: str) -> float:
    fila = con.execute(
        "SELECT score FROM marts.score_segmento WHERE objetivo = ? AND desagregacion = 'nacional'",
        [objetivo],
    ).fetchone()
    return float("nan") if fila is None else fila[0]


def anio_score(con: duckdb.DuckDBPyConnection) -> int | None:
    return con.execute("SELECT max(anio) FROM marts.score_segmento").fetchone()[0]


def indicador(con: duckdb.DuckDBPyConnection, clave: str, anio: int) -> pd.DataFrame:
    """Un indicador por departamento en un año."""
    tabla = con.execute(
        "SELECT ccdd, valor, ee, n, calidad FROM marts.indicadores "
        "WHERE indicador = ? AND anio = ? AND desagregacion = 'departamento'",
        [clave, anio],
    ).df()
    tabla["departamento"] = tabla["ccdd"].map(DEPARTAMENTOS)
    return tabla.sort_values("ccdd", ignore_index=True)


def serie_indicador(con: duckdb.DuckDBPyConnection, clave: str, ccdd: str) -> pd.DataFrame:
    """Un indicador por año, en un departamento y en el país."""
    tabla = con.execute(
        "SELECT anio, desagregacion, valor FROM marts.indicadores "
        "WHERE indicador = ? AND ((desagregacion = 'departamento' AND ccdd = ?) "
        "OR desagregacion = 'nacional') ORDER BY anio",
        [clave, ccdd],
    ).df()
    tabla["ambito"] = tabla["desagregacion"].map(
        {"departamento": DEPARTAMENTOS[ccdd], "nacional": "Perú"}
    )
    return tabla[["anio", "ambito", "valor"]]


def existe(con: duckdb.DuckDBPyConnection, tabla: str) -> bool:
    """Las tablas `variables_*` solo están en la base del dashboard, no en el almacén."""
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'marts' AND table_name = ?",
            [tabla],
        ).fetchone()[0]
    )


def tramos(con: duckdb.DuckDBPyConnection, variable: str) -> pd.DataFrame:
    if not existe(con, "variables_tramos"):
        return pd.DataFrame(columns=["orden", "tramo", "n", "tasa"])
    return con.execute(
        "SELECT orden, tramo, n, tasa_evento * 100 AS tasa FROM marts.variables_tramos "
        "WHERE variable = ? AND tasa_evento IS NOT NULL ORDER BY orden",
        [variable],
    ).df()


def tasa_desarrollo(con: duckdb.DuckDBPyConnection) -> float:
    """Tasa del evento en la cohorte de desarrollo, en %."""
    fila = con.execute(
        "SELECT sum(n * tasa_evento) / sum(n) * 100 FROM marts.variables_tramos "
        "WHERE variable = 'informal'"
    ).fetchone()
    return fila[0]


def importancia(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Information Value y peso SHAP (evento principal) de cada variable."""
    if not existe(con, "variables_iv"):
        return pd.DataFrame(columns=["variable", "iv", "shap", "nombre"])
    tabla = con.execute(
        "SELECT i.variable, i.iv, m.participacion * 100 AS shap FROM marts.variables_iv AS i "
        "LEFT JOIN marts.modelo_importancia AS m "
        "ON m.variable = i.variable AND m.objetivo = ?",
        [OBJETIVO_PRINCIPAL],
    ).df()
    tabla["nombre"] = tabla["variable"].map(NOMBRES)
    return tabla


def correlaciones(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not existe(con, "variables_correlaciones"):
        return pd.DataFrame(columns=["variable_1", "variable_2", "correlacion"])
    tabla = con.execute("SELECT * FROM marts.variables_correlaciones").df()
    tabla["nombre_1"] = tabla["variable_1"].map(NOMBRES)
    tabla["nombre_2"] = tabla["variable_2"].map(NOMBRES)
    return tabla


def calibracion(con: duckdb.DuckDBPyConnection, objetivo: str) -> pd.DataFrame:
    return con.execute(
        "SELECT tramo AS decil, n, estimado * 100 AS estimado, observado * 100 AS observado "
        "FROM marts.modelo_calibracion WHERE objetivo = ? ORDER BY tramo",
        [objetivo],
    ).df()


def metricas(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(
        "SELECT objetivo, modelo, auc, ks, brier, error_calibracion FROM marts.modelo_metricas "
        "WHERE parte = 'prueba' ORDER BY objetivo, modelo"
    ).df()


def auditoria(con: duckdb.DuckDBPyConnection, objetivo: str) -> pd.DataFrame:
    return con.execute(
        "SELECT grupo, n, observado * 100 AS observado, estimado * 100 AS estimado, auc "
        "FROM marts.modelo_auditoria WHERE objetivo = ? ORDER BY grupo",
        [objetivo],
    ).df()


def psi_maximo(con: duckdb.DuckDBPyConnection) -> float:
    return con.execute(
        "SELECT max(psi) FROM marts.modelo_estabilidad WHERE modelo = 'boosting'"
    ).fetchone()[0]


# --- gráficos ------------------------------------------------------------------------


def mapa(
    geo: list[dict],
    tabla: pd.DataFrame,
    titulo: str,
    unidad: str,
    elegido: str | None = None,
    alto: int = 560,
) -> alt.LayerChart:
    """Mapa del Perú coloreado por `tabla['valor']`, de claro (menos) a oscuro (más).

    Un clic en un departamento lo selecciona (parámetro `depto`, campo `ccdd`). El
    departamento `elegido` lleva un borde más grueso.
    """
    datos = tabla.set_index("ccdd")
    minimo, maximo = datos["valor"].min(), datos["valor"].max()
    rango = (maximo - minimo) or 1.0
    valores = []
    for f in geo:
        ccdd = f["properties"]["ccdd"]
        fila = datos.loc[ccdd] if ccdd in datos.index else None
        valor = None if fila is None or pd.isna(fila["valor"]) else float(fila["valor"])
        valores.append(
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "ccdd": ccdd,
                "departamento": DEPARTAMENTOS[ccdd],
                "lon": f["properties"]["lon"],
                "lat": f["properties"]["lat"],
                "valor": valor,
                "texto": "sin dato (poca muestra)" if valor is None else formatear(valor, unidad),
                "oscuro": bool(valor is not None and (valor - minimo) / rango > 0.55),
                "elegido": bool(ccdd == elegido),
                "afuera": ALINEACION_NOMBRES.get(ccdd) == "right",
            }
        )
    fuente = alt.Data(values=valores)
    seleccion = alt.selection_point(name="depto", fields=["ccdd"], on="click")
    formas = (
        alt.Chart(fuente)
        .mark_geoshape(stroke="#ffffff", strokeWidth=0.8)
        .encode(
            color=alt.condition(
                "isValid(datum.valor)",
                alt.Color(
                    "valor:Q",
                    scale=alt.Scale(range=RAMPA),
                    legend=alt.Legend(
                        title=titulo,
                        orient="bottom-left",
                        direction="vertical",
                        labelExpr=COMA,
                        gradientLength=140,
                    ),
                ),
                alt.value(GRIS_SIN_DATO),
            ),
            stroke=alt.condition("datum.elegido", alt.value(TINTA), alt.value("#ffffff")),
            strokeWidth=alt.condition("datum.elegido", alt.value(2.5), alt.value(0.8)),
            tooltip=[
                alt.Tooltip("departamento:N", title="Departamento"),
                alt.Tooltip("texto:N", title=titulo),
            ],
        )
        .add_params(seleccion)
    )
    capas = [formas]
    for alineacion, desplazamiento in (("center", 0), ("right", 6), ("left", -4)):
        filtro = " || ".join(
            f"datum.ccdd == '{c}'"
            for c in DEPARTAMENTOS
            if ALINEACION_NOMBRES.get(c, "center") == alineacion
        )
        capas.append(
            alt.Chart(fuente)
            .transform_filter(filtro)
            .mark_text(fontSize=10, fontWeight=500, align=alineacion, dx=desplazamiento)
            .encode(
                longitude="lon:Q",
                latitude="lat:Q",
                text="departamento:N",
                # Un nombre que sale al mar va en tinta oscura, sea cual sea el relleno.
                color=alt.condition(
                    "datum.oscuro && !datum.afuera", alt.value(TINTA_CLARA), alt.value(TINTA)
                ),
                tooltip=[
                    alt.Tooltip("departamento:N", title="Departamento"),
                    alt.Tooltip("texto:N", title=titulo),
                ],
            )
        )
    return (
        alt.layer(*capas)
        .project(type="mercator")
        .properties(height=alto)
        .configure_view(stroke=None)
    )


def barras(
    tabla: pd.DataFrame,
    categoria: str,
    valor: str = "score",
    titulo_eje: str = "Probabilidad estimada (%)",
    referencia: float | None = None,
    texto_referencia: str = "Perú",
    ordenar: bool = True,
    resaltar: str | None = None,
    alto_barra: int = 26,
) -> alt.LayerChart:
    """Barras horizontales con su valor al final y una línea gris de referencia."""
    datos = tabla.assign(
        etiqueta=tabla[valor].map(pct),
        resaltada=(tabla[categoria] == resaltar) if resaltar else False,
    )
    orden = "-x" if ordenar else None
    y = alt.Y(f"{categoria}:N", sort=orden, title=None, axis=alt.Axis(labelLimit=260))
    maximo = max(datos[valor].max(), referencia or 0) * 1.15
    x = alt.X(
        f"{valor}:Q",
        title=titulo_eje,
        scale=alt.Scale(domain=[0, maximo]),
        axis=alt.Axis(labelExpr=COMA, tickCount=5),
    )
    base = alt.Chart(datos).encode(y=y)
    color = (
        alt.condition("datum.resaltada", alt.value("#184f95"), alt.value(AZUL))
        if resaltar
        else alt.value(AZUL)
    )
    columnas = base.mark_bar(cornerRadiusEnd=4, height=alto_barra * 0.62).encode(
        x=x,
        color=color,
        tooltip=[
            alt.Tooltip(f"{categoria}:N", title=" "),
            alt.Tooltip("etiqueta:N", title="Valor"),
        ],
    )
    numeros = base.mark_text(align="left", dx=4, fontSize=11, color=TINTA).encode(
        x=x, text="etiqueta:N"
    )
    capas = [columnas]
    if referencia is not None:
        linea = pd.DataFrame(
            {"x": [referencia], "texto": [f"{texto_referencia}: {pct(referencia)}"]}
        )
        capas.append(
            alt.Chart(linea)
            .mark_rule(color=GRIS, strokeDash=[4, 3], strokeWidth=1.5)
            .encode(x="x:Q", tooltip=alt.Tooltip("texto:N", title="Referencia"))
        )
        capas.append(
            alt.Chart(linea)
            .mark_text(align="left", dx=3, dy=-4, baseline="bottom", color="#52514e", fontSize=10)
            .encode(x="x:Q", y=alt.value(0), text="texto:N")
        )
    # Las cifras van al final, con un borde blanco, para leerse sobre la línea de referencia.
    halo = base.mark_text(
        align="left", dx=4, fontSize=11, color="#ffffff", stroke="#ffffff", strokeWidth=4
    ).encode(x=x, text="etiqueta:N")
    capas += [halo, numeros]
    return alt.layer(*capas).properties(height=max(120, alto_barra * len(datos)))


def mapa_calor(tabla: pd.DataFrame, orden_filas: list[str]) -> alt.LayerChart:
    """Puntaje por departamento (filas) y rama (columnas)."""
    minimo, maximo = tabla["score"].min(), tabla["score"].max()
    datos = tabla.assign(
        etiqueta=tabla["score"].map(lambda v: f"{v:.0f}"),
        texto=tabla["score"].map(pct),
        oscuro=(tabla["score"] - minimo) / ((maximo - minimo) or 1) > 0.55,
    )
    base = alt.Chart(datos).encode(
        x=alt.X(
            "rama:N",
            sort=RAMAS,
            title=None,
            axis=alt.Axis(orient="top", labelAngle=0, labelLimit=150),
        ),
        y=alt.Y("departamento:N", sort=orden_filas, title=None),
    )
    celdas = base.mark_rect(cornerRadius=3, stroke="#ffffff", strokeWidth=2).encode(
        color=alt.Color(
            "score:Q",
            scale=alt.Scale(range=RAMPA),
            legend=alt.Legend(title="Probabilidad (%)", labelExpr=COMA, orient="right"),
        ),
        tooltip=[
            alt.Tooltip("departamento:N", title="Departamento"),
            alt.Tooltip("rama:N", title="Rama"),
            alt.Tooltip("texto:N", title="Probabilidad estimada"),
        ],
    )
    numeros = base.mark_text(fontSize=11).encode(
        text="etiqueta:N",
        color=alt.condition("datum.oscuro", alt.value(TINTA_CLARA), alt.value(TINTA)),
    )
    return alt.layer(celdas, numeros).properties(height=26 * datos["departamento"].nunique())


def serie(tabla: pd.DataFrame, titulo: str, unidad: str) -> alt.LayerChart:
    """Evolución de un indicador: el departamento en azul y el país en gris."""
    ambitos = list(dict.fromkeys(tabla["ambito"]))
    datos = tabla.assign(texto=tabla["valor"].map(lambda v: formatear(v, unidad)))
    color = alt.Color(
        "ambito:N",
        scale=alt.Scale(domain=ambitos, range=[AZUL, GRIS] if len(ambitos) > 1 else [GRIS]),
        legend=alt.Legend(title=None, orient="top"),
    )
    base = alt.Chart(datos).encode(
        x=alt.X("anio:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(
            "valor:Q",
            title=titulo,
            scale=alt.Scale(zero=False, nice=True),
            axis=alt.Axis(labelExpr=COMA),
        ),
        color=color,
    )
    lineas = base.mark_line(strokeWidth=2)
    puntos = base.mark_point(filled=True, size=70, opacity=1).encode(
        tooltip=[
            alt.Tooltip("ambito:N", title=" "),
            alt.Tooltip("anio:O", title="Año"),
            alt.Tooltip("texto:N", title=titulo),
        ]
    )
    return alt.layer(lineas, puntos).properties(height=300)


def dispersion(tabla: pd.DataFrame, titulo_x: str, unidad_x: str) -> alt.LayerChart:
    """Un punto por departamento: un indicador (x) contra el puntaje (y)."""
    datos = tabla.assign(
        texto_x=tabla["x"].map(lambda v: formatear(v, unidad_x)),
        texto_y=tabla["score"].map(pct),
    )
    base = alt.Chart(datos).encode(
        x=alt.X(
            "x:Q",
            title=titulo_x,
            scale=alt.Scale(zero=False, nice=True),
            axis=alt.Axis(labelExpr=COMA),
        ),
        y=alt.Y(
            "score:Q",
            title="Probabilidad de perder ingreso (%)",
            scale=alt.Scale(zero=False, nice=True),
            axis=alt.Axis(labelExpr=COMA),
        ),
    )
    puntos = base.mark_circle(size=90, color=AZUL, opacity=0.9).encode(
        tooltip=[
            alt.Tooltip("departamento:N", title="Departamento"),
            alt.Tooltip("texto_x:N", title=titulo_x),
            alt.Tooltip("texto_y:N", title="Probabilidad estimada"),
        ]
    )
    nombres = base.mark_text(align="left", dx=7, fontSize=10, color="#52514e").encode(
        text="departamento:N"
    )
    tendencia = base.transform_regression("x", "score").mark_line(
        color=GRIS, strokeDash=[4, 3], strokeWidth=1.5
    )
    return alt.layer(tendencia, puntos, nombres).properties(height=420)


def mapa_correlaciones(tabla: pd.DataFrame) -> alt.LayerChart:
    """Correlación de Spearman: azul negativa, rojo positiva, gris cerca de cero."""
    orden = list(dict.fromkeys(tabla["nombre_1"]))
    posicion = {nombre: i for i, nombre in enumerate(orden)}
    # Solo el triángulo inferior: la matriz es simétrica y la diagonal siempre vale 1.
    tabla = tabla[tabla["nombre_1"].map(posicion) < tabla["nombre_2"].map(posicion)]
    datos = tabla.assign(
        etiqueta=tabla["correlacion"].map(lambda v: f"{v:.2f}".replace(".", ",")),
        fuerte=tabla["correlacion"].abs() > 0.45,
    )
    base = alt.Chart(datos).encode(
        x=alt.X(
            "nombre_1:N", sort=orden, title=None, axis=alt.Axis(labelAngle=-35, labelLimit=180)
        ),
        y=alt.Y("nombre_2:N", sort=orden, title=None, axis=alt.Axis(labelLimit=200)),
    )
    celdas = base.mark_rect(stroke="#ffffff", strokeWidth=2).encode(
        color=alt.Color(
            "correlacion:Q",
            scale=alt.Scale(
                domain=[-1, 0, 1], range=["#2a78d6", "#f0efec", "#e34948"], interpolate="lab"
            ),
            legend=alt.Legend(title="Correlación", labelExpr=COMA),
        ),
        tooltip=[
            alt.Tooltip("nombre_1:N", title="Variable"),
            alt.Tooltip("nombre_2:N", title="Con"),
            alt.Tooltip("etiqueta:N", title="Correlación"),
        ],
    )
    numeros = base.mark_text(fontSize=11).encode(
        text="etiqueta:N",
        color=alt.condition("datum.fuerte", alt.value(TINTA_CLARA), alt.value(TINTA)),
    )
    return alt.layer(celdas, numeros).properties(height=420)


def barras_iv(tabla: pd.DataFrame) -> alt.LayerChart:
    """Information Value por variable, con los cortes habituales de lectura."""
    datos = tabla.assign(etiqueta=tabla["iv"].map(lambda v: f"{v:.3f}".replace(".", ",")))
    y = alt.Y("nombre:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220))
    x = alt.X("iv:Q", title="Information Value", axis=alt.Axis(labelExpr=COMA))
    columnas = (
        alt.Chart(datos)
        .mark_bar(cornerRadiusEnd=4, height=14, color=AZUL)
        .encode(
            y=y,
            x=x,
            tooltip=[
                alt.Tooltip("nombre:N", title="Variable"),
                alt.Tooltip("etiqueta:N", title="IV"),
            ],
        )
    )
    cortes = pd.DataFrame({"iv": [0.02, 0.10], "lectura": ["débil", "media"]})
    reglas = (
        alt.Chart(cortes)
        .mark_rule(color=GRIS, strokeDash=[4, 3])
        .encode(x="iv:Q", tooltip=alt.Tooltip("lectura:N", title="Desde aquí"))
    )
    rotulos = (
        alt.Chart(cortes)
        .mark_text(align="left", dx=3, dy=-4, baseline="bottom", color="#52514e", fontSize=10)
        .encode(x="iv:Q", y=alt.value(0), text="lectura:N")
    )
    return alt.layer(columnas, reglas, rotulos).properties(height=22 * len(datos))


def calibracion_grafico(tabla: pd.DataFrame) -> alt.LayerChart:
    """Por decil de riesgo estimado: lo que el modelo esperaba y lo que pasó."""
    largo = tabla.melt(
        id_vars=["decil", "n"],
        value_vars=["estimado", "observado"],
        var_name="serie",
        value_name="tasa",
    )
    largo["serie"] = largo["serie"].map(
        {"estimado": "Estimado por el modelo", "observado": "Lo que pasó"}
    )
    largo["texto"] = largo["tasa"].map(pct)
    base = alt.Chart(largo).encode(
        x=alt.X("decil:O", title="Decil de riesgo estimado (1 = menor, 10 = mayor)",
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y("tasa:Q", title="Personas que perdieron ingreso (%)",
                axis=alt.Axis(labelExpr=COMA)),
        color=alt.Color(
            "serie:N",
            scale=alt.Scale(domain=["Lo que pasó", "Estimado por el modelo"],
                            range=[AZUL, NARANJA]),
            legend=alt.Legend(title=None, orient="top"),
        ),
    )  # fmt: skip
    lineas = base.mark_line(strokeWidth=2)
    puntos = base.mark_point(filled=True, size=70, opacity=1).encode(
        tooltip=[
            alt.Tooltip("serie:N", title=" "),
            alt.Tooltip("decil:O", title="Decil"),
            alt.Tooltip("texto:N", title="Tasa"),
        ]
    )
    return alt.layer(lineas, puntos).properties(height=340)


def equidad_grafico(tabla: pd.DataFrame) -> alt.LayerChart:
    """Por sexo: tasa observada y tasa estimada, unidas por una línea."""
    largo = tabla.melt(
        id_vars=["grupo"], value_vars=["observado", "estimado"], var_name="serie", value_name="tasa"
    )
    largo["serie"] = largo["serie"].map(
        {"estimado": "Estimado por el modelo", "observado": "Lo que pasó"}
    )
    largo["texto"] = largo["tasa"].map(pct)
    y = alt.Y("grupo:N", title=None)
    x = alt.X("tasa:Q", title="Personas que perdieron ingreso (%)",
              scale=alt.Scale(zero=False, nice=True), axis=alt.Axis(labelExpr=COMA))  # fmt: skip
    union = alt.Chart(largo).mark_line(color=GRIS, strokeWidth=2).encode(y=y, x=x, detail="grupo:N")
    puntos = (
        alt.Chart(largo)
        .mark_point(filled=True, size=160, opacity=1)
        .encode(
            y=y,
            x=x,
            color=alt.Color(
                "serie:N",
                scale=alt.Scale(
                    domain=["Lo que pasó", "Estimado por el modelo"], range=[AZUL, NARANJA]
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),  # fmt: skip
            tooltip=[
                alt.Tooltip("grupo:N", title=" "),
                alt.Tooltip("serie:N", title=" "),
                alt.Tooltip("texto:N", title="Tasa"),
            ],
        )
    )
    numeros = (
        alt.Chart(largo)
        .mark_text(dy=-16, fontSize=11, color=TINTA)
        .encode(y=y, x=x, text="texto:N")
    )
    return alt.layer(union, puntos, numeros).properties(height=180)
