-- Aproximación a la morosidad por departamento, a diciembre de cada año.
-- La SBS no publica morosidad por departamento. Esta tabla promedia la morosidad de
-- cada banco con el peso de lo que ese banco coloca en el departamento.
-- Supuesto fuerte: cada banco tiene la misma morosidad en todo el país. La cifra solo
-- varía entre departamentos por la mezcla de bancos, no por el riesgo local. Cubre la
-- banca múltiple, no cajas ni financieras.
CREATE OR REPLACE TABLE marts.sbs_morosidad_proxy_departamento AS
WITH colocaciones AS (
    SELECT
        fecha_corte,
        ccdd_epen AS ccdd,
        empresa,
        regexp_replace(
            trim(regexp_replace(
                replace(lower(strip_accents(regexp_replace(empresa, '\(.*?\)', '', 'g'))), '.', ' '),
                '\s+', ' ', 'g'
            )),
            '^banco ', 'b '
        ) AS banco_llave,
        sum(saldo_miles_soles) AS saldo_miles_soles
    FROM staging.sbs_creditos_departamento
    WHERE NOT es_total_banca AND NOT es_exterior
    GROUP BY fecha_corte, ccdd_epen, empresa
)
SELECT
    year(c.fecha_corte) AS anio,
    c.fecha_corte,
    c.ccdd,
    d.departamento,
    sum(c.saldo_miles_soles * m.morosidad_pct) / sum(c.saldo_miles_soles) FILTER (
        WHERE m.morosidad_pct IS NOT NULL
    ) AS morosidad_proxy_pct,
    sum(c.saldo_miles_soles) AS credito_banca_miles_soles,
    count(*) FILTER (WHERE c.saldo_miles_soles > 0) AS bancos_con_colocaciones,
    count(*) FILTER (WHERE c.saldo_miles_soles > 0 AND m.morosidad_pct IS NULL)
        AS bancos_sin_morosidad
FROM colocaciones AS c
LEFT JOIN staging.sbs_morosidad_banco AS m
    ON c.fecha_corte = m.fecha_corte AND c.banco_llave = m.banco_llave
INNER JOIN staging.dim_departamento AS d
    ON c.ccdd = d.ccdd
GROUP BY c.fecha_corte, c.ccdd, d.departamento;
