-- Cada corte debe tener los 24 departamentos de la EPEN (Lima incluye el Callao).
SELECT anio, count(*) AS n
FROM marts.sbs_banca_departamento_anual
GROUP BY anio
HAVING count(*) <> 24
