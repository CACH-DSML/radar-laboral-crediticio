-- Créditos directos de la banca múltiple por departamento de la EPEN, a diciembre.
-- Se suma banco por banco; la fila de total de la SBS se usa solo para validar.
-- La participación excluye las sucursales en el exterior.
CREATE OR REPLACE TABLE marts.sbs_banca_departamento_anual AS
WITH por_banco AS (
    SELECT
        fecha_corte,
        ccdd_epen AS ccdd,
        empresa,
        sum(saldo_miles_soles) AS saldo_miles_soles
    FROM staging.sbs_creditos_departamento
    WHERE NOT es_total_banca AND NOT es_exterior
    GROUP BY fecha_corte, ccdd_epen, empresa
),
por_departamento AS (
    SELECT
        fecha_corte,
        ccdd,
        sum(saldo_miles_soles) AS credito_banca_miles_soles,
        count(*) FILTER (WHERE saldo_miles_soles > 0) AS bancos_con_colocaciones
    FROM por_banco
    GROUP BY fecha_corte, ccdd
)
SELECT
    year(p.fecha_corte) AS anio,
    p.fecha_corte,
    p.ccdd,
    d.departamento,
    p.credito_banca_miles_soles,
    p.credito_banca_miles_soles
    / sum(p.credito_banca_miles_soles) OVER (PARTITION BY p.fecha_corte) AS participacion_nacional,
    p.bancos_con_colocaciones
FROM por_departamento AS p
INNER JOIN staging.dim_departamento AS d
    ON p.ccdd = d.ccdd;
