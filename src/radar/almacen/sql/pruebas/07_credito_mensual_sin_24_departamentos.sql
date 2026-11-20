-- Cada mes debe tener los 24 departamentos de la EPEN (Lima incluye el Callao).
SELECT fecha, count(*) AS n
FROM marts.credito_departamento_mensual
GROUP BY fecha
HAVING count(*) <> 24
