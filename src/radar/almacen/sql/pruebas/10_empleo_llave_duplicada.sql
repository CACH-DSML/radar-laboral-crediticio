SELECT fecha, count(*) AS n
FROM marts.empleo_formal_mensual
GROUP BY fecha
HAVING count(*) > 1
