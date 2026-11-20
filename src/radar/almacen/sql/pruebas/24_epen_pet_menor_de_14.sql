-- La condición de actividad solo se mide desde los 14 años.
SELECT anio, mes, conglomerado, edad
FROM marts.epen_pet
WHERE edad IS NULL OR edad < 14
