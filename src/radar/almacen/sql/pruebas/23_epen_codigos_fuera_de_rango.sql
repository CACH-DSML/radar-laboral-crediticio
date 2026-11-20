-- Variables categóricas clave dentro del rango del diccionario.
SELECT anio, ocup300, area, estrato, c207, informal_p
FROM staging.epen_personas
WHERE ocup300 NOT IN (1, 2, 3, 4)
    OR area NOT IN (1, 2)
    OR estrato NOT BETWEEN 1 AND 8
    OR c207 NOT IN (1, 2)
    OR informal_p NOT IN (1, 2)
