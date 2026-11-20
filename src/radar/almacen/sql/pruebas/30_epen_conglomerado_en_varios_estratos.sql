-- Dentro de un año, un conglomerado pertenece a un solo departamento, estrato y área.
SELECT anio, conglomerado
FROM staging.epen_personas
GROUP BY anio, conglomerado
HAVING count(DISTINCT ccdd) > 1 OR count(DISTINCT estrato) > 1 OR count(DISTINCT area) > 1
