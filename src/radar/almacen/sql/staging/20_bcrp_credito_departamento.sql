-- Crédito directo del sistema financiero al sector privado, por departamento y moneda.
-- El nombre de la serie termina en ' - <entidad> (<moneda>)'. La entidad 'Total' es el
-- agregado nacional que publica el BCRP y se conserva para validar las sumas.
CREATE OR REPLACE TABLE staging.bcrp_credito_departamento AS
WITH base AS (
    SELECT
        fecha,
        codigo,
        regexp_extract(
            nombre_serie,
            ' - ([^-]+) \((moneda nacional|moneda extranjera|total)\)$',
            1
        ) AS entidad,
        regexp_extract(
            nombre_serie,
            '\((moneda nacional|moneda extranjera|total)\)$',
            1
        ) AS moneda,
        valor AS saldo_millones
    FROM staging.bcrp_observaciones
    WHERE grupo = 'credito_departamento'
)
SELECT
    b.fecha,
    b.codigo,
    b.entidad,
    b.entidad = 'Total' AS es_total_nacional,
    d.ccdd,
    d.ccdd_epen,
    b.moneda,
    b.saldo_millones
FROM base AS b
LEFT JOIN staging.dim_departamento AS d
    ON lower(strip_accents(b.entidad)) = lower(strip_accents(d.departamento));
