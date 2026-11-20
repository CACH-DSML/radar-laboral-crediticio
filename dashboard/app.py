"""Dashboard del Radar Laboral-Crediticio.

Arranque:
    streamlit run dashboard/app.py

Lee `radar_demo.duckdb`, la base de agregados que está junto a este archivo, y si no
existe, el almacén completo. La variable RADAR_DUCKDB elige otra base. No calcula nada
del modelo: muestra lo que ya está en la base.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import streamlit as st

from radar.catalogo import ANIOS, DEPARTAMENTOS, INDICADORES
from radar.config import VAR_ENTORNO_DUCKDB, ruta_duckdb
from radar.modelo.datos import OBJETIVO_PRINCIPAL
from radar.producto import vistas
from radar.producto.resumen_variables import NOMBRES
from radar.producto.vistas import pct

CARPETA = Path(__file__).parent
BASE_DEMO = CARPETA / "radar_demo.duckdb"
GEO = CARPETA / "peru_departamentos.geojson"

st.set_page_config(page_title="Radar Laboral-Crediticio del Perú", layout="wide")

# Con RADAR_DUCKDB se elige la base a mano. Si no, va primero la base del dashboard, que
# tiene todo lo que se muestra, y después el almacén completo.
if os.environ.get(VAR_ENTORNO_DUCKDB):
    ruta = ruta_duckdb()
else:
    ruta = BASE_DEMO if BASE_DEMO.is_file() else ruta_duckdb()
if not ruta.is_file():
    st.error(
        "No hay datos. Ejecuta `python -m radar.pipeline` o regenera la base del dashboard "
        "con `python -m radar.producto.exportar_demo`, y recarga."
    )
    st.stop()


@st.cache_resource
def conexion(ruta: str) -> duckdb.DuckDBPyConnection:
    """Una conexión por archivo: si cambia el almacén, no se reutiliza la anterior."""
    return duckdb.connect(ruta, read_only=True)


@st.cache_data
def geografia(ruta: str) -> list[dict]:
    return vistas.cargar_geo(Path(ruta))


def dec(valor: float, decimales: int = 2, signo: bool = False) -> str:
    """Número con coma decimal: 0.699 -> '0,70'."""
    return f"{valor:{'+' if signo else ''}.{decimales}f}".replace(".", ",")


def puntos(diferencia: float) -> str:
    return f"{dec(diferencia, 1, signo=True)} puntos"


def elegir_desde_mapa(clave: str) -> None:
    """Al hacer clic en el mapa, el departamento pasa a ser el elegido en todo el dashboard."""
    seleccion = st.session_state[clave]["selection"].get("depto")
    if isinstance(seleccion, list) and seleccion:
        ccdd = seleccion[0].get("ccdd")
    elif isinstance(seleccion, dict):
        ccdd = seleccion.get("ccdd")
        ccdd = ccdd[0] if isinstance(ccdd, list) and ccdd else ccdd
    else:
        ccdd = None
    if ccdd in DEPARTAMENTOS:
        st.session_state["depto"] = ccdd


con = conexion(str(ruta))
geo = geografia(str(GEO))
anio = vistas.anio_score(con)
nacional = vistas.score_nacional(con, OBJETIVO_PRINCIPAL)
por_depto = vistas.score(con, OBJETIVO_PRINCIPAL, "departamento")
if por_depto.empty:
    st.error("La base no tiene puntajes: falta panel suficiente para entrenar el modelo.")
    st.stop()
depto_rama = vistas.score(con, OBJETIVO_PRINCIPAL, "departamento_rama")
st.session_state.setdefault("depto", por_depto["ccdd"].iloc[0])

# --- encabezado ------------------------------------------------------------------------

st.title("¿Dónde es más probable perder ingreso laboral?")
st.markdown(
    f"Probabilidad de que una persona ocupada **pierda ingreso laboral en los próximos 12 "
    f"meses** (su ingreso cae 30% o más, o se queda sin trabajo), estimada con la Encuesta "
    f"Permanente de Empleo Nacional del INEI para los ocupados de {anio}. Sirve para "
    "comparar regiones, sectores y ocupaciones; no para calificar a una persona."
)
mayor, menor = por_depto.iloc[0], por_depto.iloc[-1]
combinacion = depto_rama.iloc[0] if not depto_rama.empty else None
k1, k2, k3, k4 = st.columns(4)
k1.metric("Perú", pct(nacional), help="Promedio de todos los ocupados, ponderado.")
k2.metric(
    f"Mayor riesgo: {mayor['departamento']}",
    pct(mayor["score"]),
    puntos(mayor["score"] - nacional) + " sobre Perú",
    delta_color="inverse",
)
k3.metric(
    f"Menor riesgo: {menor['departamento']}",
    pct(menor["score"]),
    puntos(menor["score"] - nacional) + " frente a Perú",
    delta_color="inverse",
)
if combinacion is not None:
    k4.metric(
        "Combinación más expuesta",
        pct(combinacion["score"]),
        f"{combinacion['departamento']} · {combinacion['rama']}",
        delta_color="off",
    )

riesgo, mercado, variables, confianza = st.tabs(
    ["Dónde está el riesgo", "Mercado laboral", "Qué explica el riesgo", "¿Funciona el modelo?"]
)

# --- 1. dónde está el riesgo -------------------------------------------------------------

with riesgo:
    nombre_evento = st.radio(
        "Evento", list(vistas.EVENTOS), horizontal=True, label_visibility="collapsed"
    )
    objetivo = vistas.EVENTOS[nombre_evento]
    deptos = vistas.score(con, objetivo, "departamento")
    base_pais = vistas.score_nacional(con, objetivo)
    izquierda, derecha = st.columns([5, 4], gap="large")
    with izquierda:
        st.subheader("Mapa del riesgo por departamento")
        st.altair_chart(
            vistas.mapa(
                geo,
                deptos.rename(columns={"score": "valor"}),
                "Probabilidad (%)",
                "porcentaje",
                elegido=st.session_state["depto"],
            ),
            width="stretch",
            key="mapa_riesgo",
            on_select=lambda: elegir_desde_mapa("mapa_riesgo"),
            selection_mode="depto",
        )
        st.caption(
            "Más oscuro, más probabilidad. Haz clic en un departamento para ver su detalle. "
            "Lima incluye al Callao, como en la encuesta."
        )
    with derecha:
        st.selectbox(
            "Departamento",
            options=sorted(DEPARTAMENTOS, key=lambda c: DEPARTAMENTOS[c]),
            format_func=DEPARTAMENTOS.get,
            key="depto",
        )
        ccdd = st.session_state["depto"]
        nombre = DEPARTAMENTOS[ccdd]
        fila = deptos[deptos["ccdd"] == ccdd]
        if fila.empty:
            st.info(f"{nombre} no tiene muestra suficiente para este evento.")
        else:
            fila = fila.iloc[0]
            puesto = int(deptos.index[deptos["ccdd"] == ccdd][0]) + 1
            st.metric(
                f"{nombre} · puesto {puesto} de {len(deptos)}",
                pct(fila["score"]),
                puntos(fila["score"] - base_pais) + " frente a Perú",
                delta_color="inverse",
            )
            ramas = vistas.score(con, objetivo, "departamento_rama")
            ramas = ramas[ramas["ccdd"] == ccdd]
            if not ramas.empty:
                alta, baja = ramas.iloc[0], ramas.iloc[-1]
                st.markdown(
                    f"En **{nombre}**, quien trabaja en **{alta['rama'].lower()}** tiene "
                    f"**{pct(alta['score'])}** de probabilidad; en "
                    f"{baja['rama'].lower()}, {pct(baja['score'])}."
                )
                st.altair_chart(vistas.barras(ramas, "rama", referencia=base_pais), width="stretch")
            ocupaciones = vistas.score(con, objetivo, "departamento_ocupacion")
            ocupaciones = ocupaciones[ocupaciones["ccdd"] == ccdd]
            if not ocupaciones.empty:
                st.markdown(f"**Por ocupación en {nombre}**")
                st.altair_chart(
                    vistas.barras(ocupaciones, "ocupacion", referencia=base_pais, alto_barra=22),
                    width="stretch",
                )

    st.divider()
    st.subheader("Departamento y sector: dónde se cruzan los riesgos")
    cruce = vistas.score(con, objetivo, "departamento_rama")
    if not cruce.empty:
        top = cruce.head(3)
        st.markdown(
            "Las combinaciones con mayor probabilidad: "
            + "; ".join(
                f"**{r.departamento} en {r.rama.lower()}** ({pct(r.score)})"
                for r in top.itertuples()
            )
            + f". El promedio del país es {pct(base_pais)}."
        )
        st.altair_chart(vistas.mapa_calor(cruce, list(deptos["departamento"])), width="stretch")
        st.caption(
            "Cada casilla es la probabilidad promedio de los ocupados de ese departamento y "
            "sector. Los departamentos van de mayor a menor riesgo."
        )
    uno, dos = st.columns(2, gap="large")
    with uno:
        st.markdown("**Por sector, en todo el país**")
        st.altair_chart(
            vistas.barras(vistas.score(con, objetivo, "rama"), "rama", referencia=base_pais),
            width="stretch",
        )
    with dos:
        st.markdown("**Por ocupación, en todo el país**")
        st.altair_chart(
            vistas.barras(
                vistas.score(con, objetivo, "ocupacion"),
                "ocupacion",
                referencia=base_pais,
                alto_barra=22,
            ),
            width="stretch",
        )

# --- 2. mercado laboral ------------------------------------------------------------------

with mercado:
    st.markdown(
        "El riesgo se apoya en cómo es el empleo en cada lugar. Aquí están los indicadores "
        "que la encuesta mide directamente, con error estándar según su diseño muestral."
    )
    c1, c2 = st.columns([3, 2])
    nombre_indicador = c1.selectbox("Indicador", list(vistas.INDICADORES_MAPA))
    clave = vistas.INDICADORES_MAPA[nombre_indicador]
    anio_ind = c2.select_slider("Año", options=list(ANIOS), value=ANIOS[-1])
    unidad = INDICADORES[clave]["unidad"]
    titulo = {"porcentaje": "%", "soles": "Soles al mes"}.get(unidad, unidad)
    valores = vistas.indicador(con, clave, anio_ind)
    izquierda, derecha = st.columns([5, 4], gap="large")
    with izquierda:
        st.altair_chart(
            vistas.mapa(geo, valores, titulo, unidad, elegido=st.session_state["depto"]),
            width="stretch",
            key="mapa_mercado",
            on_select=lambda: elegir_desde_mapa("mapa_mercado"),
            selection_mode="depto",
        )
        st.caption(
            f"{nombre_indicador}, {anio_ind}. Más oscuro, valor más alto. Gris: poca muestra. "
            "Haz clic en un departamento para ver su evolución."
        )
    with derecha:
        ccdd = st.session_state["depto"]
        st.markdown(f"**{nombre_indicador}: {DEPARTAMENTOS[ccdd]} frente al Perú**")
        st.altair_chart(
            vistas.serie(vistas.serie_indicador(con, clave, ccdd), titulo, unidad),
            width="stretch",
        )
        validos = valores.dropna(subset=["valor"]).sort_values("valor", ascending=False)
        if not validos.empty:
            alto, bajo = validos.iloc[0], validos.iloc[-1]
            st.markdown(
                f"En {anio_ind}, el valor más alto es el de **{alto['departamento']}** "
                f"({vistas.formatear(alto['valor'], unidad)}) y el más bajo, el de "
                f"**{bajo['departamento']}** ({vistas.formatear(bajo['valor'], unidad)})."
            )

    st.divider()
    st.subheader("¿Se parecen el mapa del empleo y el del riesgo?")
    x_nombre = st.selectbox(
        "Comparar el riesgo con",
        list(vistas.INDICADORES_MAPA),
        index=list(vistas.INDICADORES_MAPA.values()).index("tasa_informalidad"),
        key="x_dispersion",
    )
    x_clave = vistas.INDICADORES_MAPA[x_nombre]
    x_unidad = INDICADORES[x_clave]["unidad"]
    cruce = por_depto.merge(
        vistas.indicador(con, x_clave, anio)[["ccdd", "valor"]].rename(columns={"valor": "x"}),
        on="ccdd",
    ).dropna(subset=["x"])
    if len(cruce) > 2:
        rho = cruce["x"].corr(cruce["score"], method="spearman")
        fuerza = "fuerte" if abs(rho) >= 0.6 else "moderada" if abs(rho) >= 0.3 else "débil"
        sentido = "más" if rho > 0 else "menos"
        st.markdown(
            f"Cada punto es un departamento en {anio}. Cuanto mayor es la "
            f"{x_nombre.lower()}, {sentido} alto tiende a ser el riesgo: la relación es "
            f"{fuerza} (correlación de Spearman de {dec(rho)} entre {len(cruce)} "
            "departamentos)."
        )
        st.altair_chart(vistas.dispersion(cruce, x_nombre, x_unidad), width="stretch")

# --- 3. qué explica el riesgo ------------------------------------------------------------

with variables:
    tramos_informal = vistas.tramos(con, "informal")
    if tramos_informal.empty:
        st.info(
            "Esta base no tiene el resumen de variables. Se genera con "
            "`python -m radar.producto.exportar_demo`."
        )
    else:
        promedio = vistas.tasa_desarrollo(con)
        personas = int(tramos_informal["n"].sum())
        st.markdown(
            f"El modelo aprendió de **{vistas.numero(personas)} personas** que la encuesta "
            f"entrevistó dos veces, con un año de diferencia (primera entrevista en 2022). "
            f"El **{pct(promedio)}** perdió ingreso. Estos gráficos muestran en qué grupos "
            "pasó más seguido; la línea gris es ese promedio."
        )

        def tramo_variable(variable: str, ordenar: bool = False) -> None:
            tabla = vistas.tramos(con, variable)
            if tabla.empty:
                return
            alto, bajo = tabla.loc[tabla["tasa"].idxmax()], tabla.loc[tabla["tasa"].idxmin()]
            st.markdown(f"**{NOMBRES[variable]}**")
            if len(tabla) <= 2:
                resumen = " · ".join(f"{t.tramo}: {pct(t.tasa)}" for t in tabla.itertuples())
            else:
                resumen = (
                    f"Más alto: {alto['tramo']} ({pct(alto['tasa'])}). "
                    f"Más bajo: {bajo['tramo']} ({pct(bajo['tasa'])})."
                )
            st.caption(resumen)
            st.altair_chart(
                vistas.barras(
                    tabla,
                    "tramo",
                    valor="tasa",
                    titulo_eje="Perdió ingreso (%)",
                    referencia=promedio,
                    texto_referencia="Promedio",
                    ordenar=ordenar,
                    alto_barra=22,
                ),
                width="stretch",
            )

        st.subheader("¿Quién pierde ingreso más seguido?")
        filas = [
            [("informal", False), ("nivel_educativo", False)],
            [("edad", False), ("horas_semana", False)],
            [("ocupacion_gran_grupo", True), ("log_ingreso", False)],
        ]
        for fila in filas:
            columnas = st.columns(2, gap="large")
            for columna, (variable, ordenar) in zip(columnas, fila, strict=True):
                with columna:
                    tramo_variable(variable, ordenar)
        otras = {
            NOMBRES[v]: v
            for v in (
                "area_nombre",
                "ciiu_seccion",
                "ccdd",
                "categoria_ocupacional",
                "log_trabajadores",
                "afiliado_pension",
                "quiere_mas_horas",
                "busca_otro_trabajo",
            )
        }
        elegida = st.selectbox("Ver otra variable", list(otras))
        with st.columns(2)[0]:
            tramo_variable(otras[elegida], ordenar=otras[elegida] in ("ciiu_seccion", "ccdd"))

        st.divider()
        st.subheader("¿Por qué estas variables?")
        st.markdown(
            "Todas describen a la persona **en la primera entrevista**: nada de lo que pasa "
            "después entra al modelo. No se usan sexo, lengua materna ni autoidentificación "
            "étnica; el sexo solo se usa para auditar el resultado."
        )
        pesos = vistas.importancia(con)
        uno, dos = st.columns(2, gap="large")
        with uno:
            st.markdown("**Cuánto separa cada variable por sí sola** (Information Value)")
            st.altair_chart(vistas.barras_iv(pesos), width="stretch")
            st.caption(
                "Mide cuánto distingue una variable, sola, a quien pierde ingreso de quien "
                "no. Menos de 0,02 se considera que no separa; desde 0,10, que separa de "
                "forma media."
            )
        with dos:
            st.markdown("**Cuánto la usa el modelo** (participación en los valores SHAP)")
            st.altair_chart(
                vistas.barras(
                    pesos.dropna(subset=["shap"]),
                    "nombre",
                    valor="shap",
                    titulo_eje="Peso en el modelo (%)",
                    alto_barra=22,
                ),
                width="stretch",
            )
            ingreso = pesos.set_index("variable").loc["log_ingreso"]
            st.caption(
                f"El ingreso separa poco por sí solo (IV de {dec(ingreso['iv'], 3)}"
                f") pero es lo que más usa el modelo ({pct(ingreso['shap'])}). Su relación "
                "con el evento no es una línea recta (ver el gráfico de ingreso arriba) y "
                "depende de las demás variables, algo que el modelo sí capta."
            )

        st.divider()
        st.subheader("¿Cómo se relacionan entre sí?")
        corr = vistas.correlaciones(con)
        pares = corr[corr["variable_1"] < corr["variable_2"]]
        con_evento = pares[
            (pares["variable_1"] == OBJETIVO_PRINCIPAL)
            | (pares["variable_2"] == OBJETIVO_PRINCIPAL)
        ]
        entre = pares.drop(con_evento.index)
        fuerte = entre.loc[entre["correlacion"].abs().idxmax()]
        maximo_evento = con_evento["correlacion"].abs().max()
        st.markdown(
            f"La pareja más relacionada es **{fuerte['nombre_1'].lower()}** y "
            f"**{fuerte['nombre_2'].lower()}** ({dec(fuerte['correlacion'])})."
            " La informalidad, la afiliación a pensiones, el ingreso y el tamaño de la "
            "empresa se mueven juntos: en parte miden lo mismo, qué tan formal es el empleo. "
            f"Ninguna variable se relaciona fuerte con el evento (máximo "
            f"{dec(maximo_evento)}): "
            "ninguna basta sola, y por eso el modelo las combina."
        )
        with st.columns([3, 1])[0]:
            st.altair_chart(vistas.mapa_correlaciones(corr), width="stretch")
        st.caption(
            "Correlación de Spearman en la cohorte de desarrollo. Rojo: suben juntas. Azul: "
            "cuando una sube, la otra baja."
        )

# --- 4. ¿funciona el modelo? -------------------------------------------------------------

with confianza:
    tabla_metricas = vistas.metricas(con)
    principal = tabla_metricas[tabla_metricas["objetivo"] == OBJETIVO_PRINCIPAL].set_index("modelo")
    deciles = vistas.calibracion(con, OBJETIVO_PRINCIPAL)
    if principal.empty or deciles.empty:
        st.info("La base no tiene las métricas del modelo.")
    else:
        st.markdown(
            "El modelo se entrenó con quienes fueron entrevistados por primera vez en 2022 y "
            "se evalúa con los de **2024**, personas que nunca vio. Así se prueba como se "
            "usaría: prediciendo hacia adelante."
        )
        auc = principal.loc["boosting", "auc"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "AUC del modelo",
            dec(auc),
            f"{dec(auc - principal.loc['logistico', 'auc'], signo=True)} "
            "frente a una regresión logística",
            help="Probabilidad de que, entre una persona que perdió ingreso y otra que no, "
            "el modelo le asigne más riesgo a la primera. 0,5 es azar; 1 es perfecto.",
        )
        m2.metric("10% con más riesgo estimado", pct(deciles["observado"].iloc[-1]),
                  "perdió ingreso", delta_color="off")  # fmt: skip
        m3.metric("10% con menos riesgo estimado", pct(deciles["observado"].iloc[0]),
                  "perdió ingreso", delta_color="off")  # fmt: skip
        psi = vistas.psi_maximo(con)
        m4.metric(
            "Estabilidad (PSI)",
            dec(psi, 3),
            "estable" if psi < 0.10 else "revisar",
            delta_color="normal" if psi < 0.10 else "inverse",
            help="Cambio en la distribución del puntaje entre cohortes. Menos de 0,10 es estable.",
        )
        st.markdown(
            f"Un AUC de {dec(auc)} ordena bien a {round(auc * 100)} de cada 100 parejas. "
            "Es una discriminación moderada: el ingreso que se declara en una encuesta varía "
            "mucho de un año a otro y parte de esa variación es ruido que nada predice."
        )

        izquierda, derecha = st.columns(2, gap="large")
        with izquierda:
            st.subheader("¿Acierta el nivel?")
            st.altair_chart(vistas.calibracion_grafico(deciles), width="stretch")
            sesgo = (deciles["estimado"] - deciles["observado"]).mul(deciles["n"]).sum() / deciles[
                "n"
            ].sum()
            st.caption(
                "Se ordena a las personas de 2024 por su riesgo estimado y se parten en diez "
                "grupos iguales. Si las dos líneas van juntas, el modelo acierta el nivel. "
                f"En promedio estima {dec(abs(sesgo), 1)} puntos "
                + ("de más" if sesgo > 0 else "de menos")
                + ": el evento fue menos frecuente en 2024 que en la cohorte con la que se "
                "calibró."
            )
        with derecha:
            st.subheader("¿Trata igual a hombres y mujeres?")
            sexo = vistas.auditoria(con, OBJETIVO_PRINCIPAL)
            if not sexo.empty:
                st.altair_chart(vistas.equidad_grafico(sexo), width="stretch")
                s = sexo.set_index("grupo")
                if {"Hombre", "Mujer"} <= set(s.index):
                    dif_m = s.loc["Mujer", "estimado"] - s.loc["Mujer", "observado"]
                    dif_h = s.loc["Hombre", "estimado"] - s.loc["Hombre", "observado"]
                    st.markdown(
                        f"El modelo no usa el sexo. Ordena casi igual de bien a ambos (AUC "
                        f"{dec(s.loc['Hombre', 'auc'])} y {dec(s.loc['Mujer', 'auc'])}), "
                        "pero no acierta el nivel: las mujeres pierden ingreso más seguido "
                        f"y el modelo las estima {dec(abs(dif_m), 1)} puntos por debajo; "
                        f"a los hombres, {dec(abs(dif_h), 1)} por encima. "
                        "Un segmento con muchas mujeres recibe un puntaje algo optimista."
                    )

        st.divider()
        st.subheader("Límites")
        st.markdown(
            "- **No es un modelo de crédito.** Mide pérdida de ingreso laboral, no impago.\n"
            "- **Ingreso nominal.** La caída de 30% no descuenta la inflación.\n"
            "- **Solo quien sigue en la encuesta.** Se observa a quienes fueron "
            "reentrevistados a los 12 meses.\n"
            "- **Poca historia.** Una sola cohorte de desarrollo y ninguna recesión en el "
            "periodo.\n"
            "- **Sin validación externa sólida.** La SBS no publica morosidad por "
            "departamento."
        )

st.divider()
st.caption(
    "Fuente: INEI, Encuesta Permanente de Empleo Nacional (EPEN), 2022 a 2025. Microdatos "
    "públicos con licencia ODbL. Límites departamentales: "
    "geoBoundaries (dominio público). El detalle del modelo está en el notebook y el README "
    "del proyecto."
)
