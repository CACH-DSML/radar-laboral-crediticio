-- Filas sin llave de panel: no se pueden seguir en el tiempo.
SELECT anio, mes, conglomerado, selviv, hogar, c201
FROM staging.epen_personas
WHERE llave_panel IS NULL
