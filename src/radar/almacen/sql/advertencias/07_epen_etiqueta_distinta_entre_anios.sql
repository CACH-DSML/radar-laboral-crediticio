-- Códigos de ocupación o actividad cuya etiqueta cambia de un año a otro.
SELECT upper(variable) AS variable, codigo, count(DISTINCT trim(etiqueta)) AS etiquetas
FROM raw.epen_etiquetas
WHERE upper(variable) IN ('C308_COD', 'C309_COD')
GROUP BY upper(variable), codigo
HAVING count(DISTINCT trim(etiqueta)) > 1
