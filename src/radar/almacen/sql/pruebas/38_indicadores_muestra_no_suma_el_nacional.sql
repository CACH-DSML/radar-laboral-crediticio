-- Cada desagregación reparte a todos los ocupados: la muestra de sus celdas debe sumar
-- la muestra nacional del mismo indicador.
WITH por_desagregacion AS (
    SELECT anio, desagregacion, indicador, sum(n) AS n
    FROM marts.indicadores
    GROUP BY anio, desagregacion, indicador
)
SELECT d.anio, d.desagregacion, d.indicador, d.n, nacional.n AS n_nacional
FROM por_desagregacion AS d
INNER JOIN por_desagregacion AS nacional
    ON d.anio = nacional.anio
    AND d.indicador = nacional.indicador
    AND nacional.desagregacion = 'nacional'
WHERE d.n <> nacional.n
