-- Los catálogos tienen una fila por código.
SELECT 'actividad' AS catalogo, ciiu_clase AS codigo, count(*) AS filas
FROM staging.dim_actividad
GROUP BY ciiu_clase
HAVING count(*) > 1
UNION ALL
SELECT 'ocupacion', ocupacion, count(*)
FROM staging.dim_ocupacion
GROUP BY ocupacion
HAVING count(*) > 1
