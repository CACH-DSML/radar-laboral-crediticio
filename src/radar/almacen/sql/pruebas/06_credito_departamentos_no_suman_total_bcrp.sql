-- La suma de los departamentos debe coincidir con el total nacional que publica el BCRP
-- (tolerancia relativa de 0.5%).
WITH suma AS (
    SELECT fecha, moneda, sum(saldo_millones) AS suma_departamentos
    FROM staging.bcrp_credito_departamento
    WHERE NOT es_total_nacional
    GROUP BY fecha, moneda
),
total AS (
    SELECT fecha, moneda, saldo_millones AS total_publicado
    FROM staging.bcrp_credito_departamento
    WHERE es_total_nacional
)
SELECT s.fecha, s.moneda, s.suma_departamentos, t.total_publicado
FROM suma AS s
INNER JOIN total AS t USING (fecha, moneda)
WHERE abs(s.suma_departamentos - t.total_publicado) > 0.005 * abs(t.total_publicado)
