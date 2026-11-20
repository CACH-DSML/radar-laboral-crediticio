-- Una persona aparece una sola vez por visita: año, mes, conglomerado, muestra,
-- vivienda, hogar y número de orden.
SELECT anio, mes, conglomerado, muestra, selviv, hogar, c201, count(*) AS filas
FROM staging.epen_personas
GROUP BY anio, mes, conglomerado, muestra, selviv, hogar, c201
HAVING count(*) > 1
