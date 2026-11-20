-- Estructura de los créditos directos de la banca múltiple por departamento (SBS, B-2349).
-- porcentaje: parte de los créditos del banco colocada en ese departamento.
-- saldo_miles_soles: porcentaje aplicado al total de créditos del banco.
CREATE OR REPLACE TABLE staging.sbs_creditos_departamento AS
SELECT
    CAST(r.fecha_corte AS DATE) AS fecha_corte,
    r.empresa,
    r.empresa LIKE 'TOTAL%' AS es_total_banca,
    r.columna,
    r.columna LIKE 'Sucursales%' AS es_exterior,
    d.ccdd,
    d.ccdd_epen,
    CAST(r.porcentaje AS DOUBLE) AS porcentaje,
    CAST(r.total_miles_soles AS DOUBLE) AS total_miles_soles,
    CAST(r.porcentaje AS DOUBLE) / 100 * CAST(r.total_miles_soles AS DOUBLE) AS saldo_miles_soles,
    r.archivo
FROM raw.sbs_creditos_departamento AS r
LEFT JOIN staging.dim_departamento AS d
    ON lower(strip_accents(r.columna)) = lower(strip_accents(d.departamento));
