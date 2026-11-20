-- Morosidad de cada banco a diciembre: créditos atrasados (criterio SBS) sobre créditos
-- directos, en porcentaje. `banco_llave` es el nombre normalizado para cruzar con el
-- cuadro de créditos por departamento, que escribe algunos nombres de otra forma.
CREATE OR REPLACE TABLE staging.sbs_morosidad_banco AS
WITH normalizado AS (
    SELECT
        CAST(fecha_corte AS DATE) AS fecha_corte,
        trim(empresa) AS empresa,
        regexp_replace(
            trim(regexp_replace(
                replace(lower(strip_accents(regexp_replace(empresa, '\(.*?\)', '', 'g'))), '.', ' '),
                '\s+', ' ', 'g'
            )),
            '^banco ', 'b '
        ) AS llave,
        CAST(morosidad_pct AS DOUBLE) AS morosidad_pct
    FROM raw.sbs_morosidad_banco
)
SELECT
    fecha_corte,
    empresa,
    -- El mismo banco figura como "Bank of China" en un cuadro y "B. China Perú" en otro.
    CASE llave WHEN 'b china peru' THEN 'bank of china' ELSE llave END AS banco_llave,
    morosidad_pct,
    llave LIKE 'total%' AS es_total_banca
FROM normalizado;
