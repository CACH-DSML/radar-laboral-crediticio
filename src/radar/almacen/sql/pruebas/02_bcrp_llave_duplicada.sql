-- Una sola observación por serie y mes.
SELECT codigo, fecha, count(*) AS n
FROM staging.bcrp_observaciones
GROUP BY codigo, fecha
HAVING count(*) > 1
