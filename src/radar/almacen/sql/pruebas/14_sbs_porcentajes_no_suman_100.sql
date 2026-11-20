-- La estructura de cada banco con créditos debe sumar 100% (tolerancia de 0.01 puntos).
SELECT fecha_corte, empresa, sum(porcentaje) AS suma
FROM staging.sbs_creditos_departamento
WHERE total_miles_soles > 0
GROUP BY fecha_corte, empresa
HAVING abs(sum(porcentaje) - 100) > 0.01
