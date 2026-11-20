-- El factor de expansión no puede ser negativo.
SELECT anio, mes, conglomerado, factor
FROM marts.epen_pet
WHERE factor < 0
