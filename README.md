# Radar Laboral-Crediticio del Perú

**Demo:** [dashboard en Streamlit](https://radar-laboral-crediticio-bvvssmy6tkuxpgzcgfamhn.streamlit.app/)  
**Validación del modelo:** [notebook de desarrollo y validación](desarrollo_y_validacion_modelo.ipynb)

Convierte los microdatos de la Encuesta Permanente de Empleo Nacional (EPEN, INEI) en
señales de vulnerabilidad del ingreso por departamento, sector y ocupación, pensadas
para el análisis de riesgo en banca. Todo sale de datos públicos y se reconstruye con un
comando.

## El problema

Un banco que quiere saber qué tan frágil es el ingreso de un segmento de clientes suele
mirar su propia cartera, que solo conoce a quien ya es cliente. La encuesta de empleo
del INEI observa a todos los trabajadores y vuelve a entrevistar a las mismas personas
un año después. Eso permite medir algo que una foto no muestra: quién pierde ingreso.

Este proyecto no predice impago: no hay datos crediticios individuales. Estima la
probabilidad de que una persona ocupada pierda ingreso laboral en 12 meses y la resume
por segmento.

## Cómo está organizado

```
├── desarrollo_y_validacion_modelo.ipynb   documento principal: datos, modelo y validación
├── dashboard/
│   ├── app.py                             dashboard en Streamlit
│   ├── radar_demo.duckdb                  agregados que muestra el dashboard (4,5 MB)
│   └── peru_departamentos.geojson         límites departamentales del mapa
├── data/                                  base final y almacén; se generan en local (ver data/README.md)
├── src/radar/                             código que usan el notebook y el dashboard
│   ├── ingesta/                           lectura de la EPEN, el BCRP y la SBS
│   ├── almacen/                           almacén DuckDB en SQL, con 43 pruebas de calidad
│   ├── indicadores/                       indicadores con error estándar según el diseño muestral
│   ├── nowcast/                           estimación trimestral del empleo
│   ├── modelo/                            base final, entrenamiento, métricas y validación
│   └── api/                               API de solo lectura (FastAPI)
├── pyproject.toml                         dependencias del proyecto
└── requirements.txt                       dependencias para publicar el dashboard
```

## Resultados

**El almacén reproduce al INEI.** Los totales expandidos coinciden con 66 cifras anuales y
46 trimestrales publicadas por el INEI. Ocupados de 2025: 17 575,2 miles, la cifra
oficial. Los errores estándar, calculados por linealización de Taylor con conglomerados
dentro de estratos, replican 1 120 estimaciones hechas con `svy` en Stata.

**La precisión limita el detalle.** Una celda con menos de 30 casos, o con coeficiente de
variación de 30% o más, no se publica. La informalidad por departamento y rama (120
celdas) es publicable completa; el cruce de departamento, sección y ocupación solo en 724
de 2 929 celdas.

**El nowcast mejora al baseline, con poca evidencia.** Una ecuación puente con los puestos
formales del BCRP reduce el error en 22% para los ocupados y en 34% para la
informalidad, sobre ocho trimestres fuera de muestra.

**El modelo discrimina de forma moderada** (AUC 0,70) y es estable entre cohortes. El
puntaje va de 34,9% en servicios a 45,8% en agricultura, pesca y minería, y de 33,9% en
La Libertad a 47,4% en Puno.

**Un hallazgo incómodo.** El modelo no usa el sexo. Por eso subestima el riesgo de las
mujeres en 2,7 puntos y sobreestima el de los hombres en 7,4: ellas pierden ingreso con
más frecuencia y el modelo no lo ve.

## Ficha del modelo

El detalle de cada punto, con tablas y gráficos, está en el
[notebook](desarrollo_y_validacion_modelo.ipynb).

**Qué estima.** La probabilidad de que una persona ocupada pierda ingreso laboral en los
12 meses siguientes: que deje de estar ocupada o que su ingreso por trabajo caiga 30% o
más. Como contraste se modela solo la pérdida de empleo, que no depende del ingreso
declarado.

**Uso previsto.** Ordenar segmentos laborales (departamento, rama, ocupación) por la
fragilidad de su ingreso, como insumo de un análisis de riesgo de cartera. **No sirve**
para calificar a una persona, aprobar o negar un crédito, ni estimar impago.

**Datos.** EPEN 2022 a 2025. Una fila por persona ocupada con ingreso, observada dos veces
con 12 meses de diferencia: 143 804 personas. Partición fuera de tiempo, por año de la
primera visita; nadie aparece en dos partes:

| Parte | Cohorte | Personas | Evento observado |
|---|---|---|---|
| Desarrollo | 2022 | 51 193 | 37,8% |
| Calibración y parada temprana | 2023 | 45 535 | 38,3% |
| Prueba fuera de tiempo | 2024 | 47 076 | 36,4% |

**Variables.** Veinte, todas de la primera visita: edad, ingreso, horas, tamaño de la
empresa, informalidad, afiliación a pensiones, seguro de salud, educación, departamento,
área, sección de actividad, gran grupo de ocupación, categoría ocupacional, tipo de
empleador, registro en la Sunat, frecuencia de pago, deseo de más horas, búsqueda de otro
trabajo y trimestre. No se usan sexo, lengua materna ni autoidentificación étnica; el
sexo se conserva solo para auditar el modelo.

**Modelos.** Un baseline logístico y un LightGBM (214 árboles, con parada temprana), ambos
calibrados con regresión isotónica sobre la cohorte 2023.

**Resultados en la cohorte de prueba (2024):**

| Evento | Modelo | AUC | Gini | KS | Brier | Error de calibración |
|---|---|---|---|---|---|---|
| Pérdida de ingreso (30%) | Logístico | 0,654 | 0,309 | 0,221 | 0,216 | 0,024 |
| Pérdida de ingreso (30%) | **LightGBM** | **0,699** | **0,398** | **0,282** | **0,206** | **0,025** |
| Pérdida de ingreso (50%) | LightGBM | 0,711 | 0,422 | 0,302 | 0,180 | 0,024 |
| Pérdida de empleo | LightGBM | 0,755 | 0,509 | 0,378 | 0,115 | 0,008 |

Un AUC de 0,70 ordena bien 70 de cada 100 pares formados por una persona que perdió
ingreso y otra que no. El ingreso declarado en una encuesta varía mucho de una visita a
otra, y parte de esa variación es ruido que nada puede predecir.

**Calibración.** El orden se sostiene: el 10% con mayor puntaje tiene una tasa observada
de 68,3% y el 10% con menor, de 11,8%. El modelo sobreestima 2,5 puntos en promedio,
porque el evento fue menos frecuente en 2024 que en la cohorte de calibración.

**Estabilidad.** El PSI del puntaje entre la cohorte de desarrollo y las otras dos es
menor que 0,005 (menos de 0,10 es estable). Por variable, solo el registro en la Sunat
cambia entre 2022 y 2023 (CSI 0,19), por un código que aparece solo en la base de 2023.

**Qué pesa.** Según los valores SHAP, el ingreso (21,7%), la edad (11,0%), la informalidad
(10,7%) y las horas trabajadas (8,1%). Parte del peso del ingreso es mecánico: quien
declaró un ingreso alto por azar tiende a declarar menos la vez siguiente. En el modelo
de pérdida de empleo pesan primero las horas (18,4%), la edad (15,4%) y el ingreso
(12,5%); la informalidad, la ocupación y el departamento importan en ambos.

**Equidad.** Ordena igual de bien a hombres y mujeres (AUC de 0,70 en ambos), pero no
acierta el nivel:

| | Evento observado | Estimado |
|---|---|---|
| Hombres | 31,6% | 39,0% |
| Mujeres | 41,6% | 38,9% |

Un segmento con muchas mujeres recibe un puntaje algo optimista.

**Puntaje por segmento.** El producto final es el promedio de la probabilidad estimada de
los ocupados de 2025 en cada segmento, ponderado por el factor de expansión, con su error
estándar muestral. Nacional: 39,5%.

**Validación externa.** La SBS no publica morosidad por departamento. Con una aproximación
(la morosidad de cada banco, ponderada por lo que coloca en cada departamento), la
correlación de Spearman con el puntaje es de 0,27 entre 24 departamentos. No valida ni
refuta el modelo: la aproximación casi no varía (de 3,2% a 3,8%).

**Limitaciones.**

- No es un modelo de crédito: mide pérdida de ingreso laboral, no impago.
- Ingreso nominal: la caída de 30% no descuenta la inflación.
- Solo se observa a quienes siguen en el panel de la encuesta a los 12 meses.
- Una sola cohorte de desarrollo y ninguna recesión en el periodo.
- El puntaje de 2025 aplica a ocupados de 2025 un modelo entrenado con 2022.
- Sesgo de nivel por sexo, descrito arriba.
- Sin validación externa sólida, por falta de morosidad departamental.

## Cómo reproducir

Requiere Python 3.11 o superior.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[producto,notebooks]"
```

**Solo el dashboard.** No necesita microdatos: usa la base de agregados que está en
`dashboard/`. Tiene cuatro pestañas: el mapa del riesgo por departamento y su cruce con
el sector y la ocupación, los indicadores del mercado laboral, qué variables explican el
riesgo y por qué se eligieron, y qué tan confiable es el modelo.

```powershell
.venv\Scripts\python -m streamlit run dashboard/app.py
```

**Todo desde los microdatos.** Descarga la EPEN como explica
[data/README.md](data/README.md) y ejecuta:

```powershell
.venv\Scripts\python -m radar.pipeline
```

Descarga BCRP y SBS, arma el almacén, corre las pruebas de calidad, entrena el modelo y
escribe la base final en `data/base_modelo.csv`. Tarda unos dos minutos. Después se
pueden ejecutar el notebook y regenerar la base del dashboard:

```powershell
.venv\Scripts\python -m jupyter nbconvert --to notebook --execute --inplace desarrollo_y_validacion_modelo.ipynb
.venv\Scripts\python -m radar.producto.exportar_demo
```

La API se levanta con `.venv\Scripts\python -m uvicorn radar.api.app:app`; su
documentación queda en `http://localhost:8000/docs`.

## Licencia

El código se publica bajo licencia MIT. Los microdatos de la EPEN pertenecen al INEI y se
publican en la Plataforma Nacional de Datos Abiertos bajo licencia ODbL.
`dashboard/radar_demo.duckdb` contiene agregados derivados de la EPEN y mantiene esa
licencia. Los límites de `dashboard/peru_departamentos.geojson` vienen de
[geoBoundaries](https://www.geoboundaries.org) (dominio público), simplificados y con
Lima y el Callao unidos, como en la encuesta. La estructura de la CIIU Revisión 4 incluida en `src/radar/almacen/semillas` es
de Naciones Unidas.
