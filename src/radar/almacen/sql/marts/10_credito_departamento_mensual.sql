-- Crédito directo al sector privado por mes y departamento de la EPEN.
-- La EPEN publica Lima con el Callao incluido (CCDD 15), así que aquí se suman ambos.
--
-- El total se calcula como moneda nacional más moneda extranjera. La serie 'total' que
-- publica el BCRP se conserva aparte porque en algunos meses no coincide con esa suma
-- (el caso mayor es julio de 2021).
-- var_12m compara con el mismo mes del año anterior.
CREATE OR REPLACE TABLE marts.credito_departamento_mensual AS
WITH agregado AS (
    SELECT
        fecha,
        ccdd_epen AS ccdd,
        sum(saldo_millones) FILTER (WHERE moneda = 'moneda nacional') AS credito_mn_millones,
        sum(saldo_millones) FILTER (WHERE moneda = 'moneda extranjera') AS credito_me_millones,
        sum(saldo_millones) FILTER (WHERE moneda = 'total') AS credito_total_publicado_millones
    FROM staging.bcrp_credito_departamento
    WHERE NOT es_total_nacional
    GROUP BY fecha, ccdd_epen
),
con_total AS (
    SELECT
        *,
        credito_mn_millones + credito_me_millones AS credito_total_millones
    FROM agregado
)
SELECT
    a.fecha,
    a.ccdd,
    d.departamento,
    a.credito_total_millones,
    a.credito_mn_millones,
    a.credito_me_millones,
    a.credito_me_millones / nullif(a.credito_total_millones, 0) AS dolarizacion,
    a.credito_total_millones / nullif(p.credito_total_millones, 0) - 1 AS var_12m,
    a.credito_total_publicado_millones,
    abs(a.credito_total_publicado_millones - a.credito_total_millones)
    > 0.0001 * a.credito_total_millones AS total_publicado_inconsistente
FROM con_total AS a
INNER JOIN staging.dim_departamento AS d
    ON a.ccdd = d.ccdd
LEFT JOIN con_total AS p
    ON a.ccdd = p.ccdd AND p.fecha = a.fecha - INTERVAL 12 MONTH;
