-- Ningún componente de la llave ni del diseño muestral puede faltar.
SELECT anio, mes, conglomerado, selviv, hogar, c201
FROM staging.epen_personas
WHERE anio IS NULL OR mes IS NULL OR mes NOT BETWEEN 1 AND 12
    OR conglomerado IS NULL OR conglomerado = '' OR muestra IS NULL
    OR selviv IS NULL OR hogar IS NULL OR c201 IS NULL
    OR estrato IS NULL OR area IS NULL OR ccdd IS NULL
