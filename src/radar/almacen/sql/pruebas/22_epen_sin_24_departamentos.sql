-- Cada año debe traer los 24 departamentos de la EPEN (el Callao va dentro de Lima).
SELECT anio, count(DISTINCT ccdd) AS departamentos
FROM marts.epen_pet
GROUP BY anio
HAVING count(DISTINCT ccdd) <> 24
