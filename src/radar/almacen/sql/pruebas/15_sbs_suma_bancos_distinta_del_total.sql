-- La suma banco por banco debe coincidir con la fila de total de la SBS
-- (tolerancia relativa de 0.1%).
WITH bancos AS (
    SELECT fecha_corte, columna, sum(saldo_miles_soles) AS suma_bancos
    FROM staging.sbs_creditos_departamento
    WHERE NOT es_total_banca
    GROUP BY fecha_corte, columna
),
total AS (
    SELECT fecha_corte, columna, saldo_miles_soles AS total_publicado
    FROM staging.sbs_creditos_departamento
    WHERE es_total_banca
)
SELECT b.fecha_corte, b.columna, b.suma_bancos, t.total_publicado
FROM bancos AS b
INNER JOIN total AS t USING (fecha_corte, columna)
WHERE abs(b.suma_bancos - t.total_publicado) > 0.001 * abs(t.total_publicado) + 1
