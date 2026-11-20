SELECT fecha, ccdd, count(*) AS n
FROM marts.credito_departamento_mensual
GROUP BY fecha, ccdd
HAVING count(*) > 1
