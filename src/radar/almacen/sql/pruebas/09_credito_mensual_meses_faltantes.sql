-- La serie de cada departamento no debe tener huecos entre su primer y último mes.
SELECT ccdd, count(*) AS meses, min(fecha) AS desde, max(fecha) AS hasta
FROM marts.credito_departamento_mensual
GROUP BY ccdd
HAVING count(*) <> datediff('month', min(fecha), max(fecha)) + 1
