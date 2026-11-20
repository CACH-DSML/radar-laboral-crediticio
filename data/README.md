# Datos

Esta carpeta no se sube al repositorio, salvo este archivo. Contiene microdatos de
personas, aunque sean públicos y anónimos, y se regenera con un comando.

## Qué hay aquí después de correr el pipeline

| Archivo | Qué es |
|---|---|
| `base_modelo.csv` | **Base final del modelo.** Una fila por persona (143 804): sus variables en la primera visita y lo que le pasó 12 meses después. Es la que lee el notebook |
| `radar.duckdb` | Almacén completo: capas `raw`, `staging` y `marts` (unos 400 MB) |
| `raw/` | Archivos tal como los entrega cada fuente |

El dashboard no usa esta carpeta: lee `dashboard/radar_demo.duckdb`, que solo tiene
agregados.

## Cómo se genera

1. Descarga las bases anuales 2022 a 2025 de la EPEN en formato Stata (`.dta`) desde el
   [catálogo de datos abiertos](https://www.datosabiertos.gob.pe/) (buscar "Encuesta
   Permanente de Empleo Nacional EPEN Departamentos") o desde el servidor de microdatos
   del INEI. Déjalas en una carpeta `EPEN` junto al repositorio, o define `RADAR_EPEN_DIR`.
2. Ejecuta:

   ```powershell
   .venv\Scripts\python -m radar.pipeline
   ```

   Descarga las series del BCRP y los cuadros de la SBS, lee la EPEN, arma el almacén,
   corre 43 pruebas de calidad, entrena el modelo y escribe `base_modelo.csv`.

Para volver a escribir solo la base final desde un almacén ya construido:
`python -m radar.modelo.base`.

## Fuentes

| Fuente | Qué se usa | Acceso |
|---|---|---|
| **EPEN** (INEI), 2022 a 2025 | Microdatos de empleo: la única encuesta del proyecto | [datosabiertos.gob.pe](https://www.datosabiertos.gob.pe/) y [proyectos.inei.gob.pe/microdatos](https://proyectos.inei.gob.pe/microdatos/) |
| **BCRP** | Crédito por departamento y puestos de trabajo formales, mensuales | [API de BCRPData](https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api), descarga automática |
| **SBS** | Créditos por departamento y morosidad por banco, a diciembre | Cuadros B-2349 (créditos por departamento y banco) y B-2401 (indicadores por banco), descarga automática |
| **Clasificadores** | CIIU Rev. 4 (Naciones Unidas) y grandes grupos de la CNO 2015 (INEI) | En `src/radar/almacen/semillas/` |
| **Cifras oficiales del INEI** | Totales publicados para validar la ingesta | En `src/radar/almacen/semillas/` |

## Licencia y cita

Las bases de la EPEN se publican bajo licencia Open Database License (ODbL): se pueden
usar y adaptar citando la fuente, y las bases derivadas que se publiquen mantienen esa
licencia. Cita: "INEI, Encuesta Permanente de Empleo Nacional (EPEN), {año}".
