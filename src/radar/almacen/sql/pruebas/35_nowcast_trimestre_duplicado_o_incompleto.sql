-- La base del nowcast tiene una fila por trimestre, y cada año de la EPEN trae sus
-- cuatro trimestres.
SELECT 'trimestre duplicado' AS problema, CAST(fecha AS VARCHAR) AS detalle
FROM marts.nowcast_trimestral
GROUP BY fecha
HAVING count(*) > 1
UNION ALL
SELECT 'año de la EPEN sin cuatro trimestres', CAST(anio AS VARCHAR)
FROM marts.nowcast_trimestral
WHERE ocupados_miles IS NOT NULL
GROUP BY anio
HAVING count(*) <> 4
