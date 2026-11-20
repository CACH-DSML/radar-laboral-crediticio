-- Ocupados sin dato de ingreso total (ingtrabw).
SELECT anio, mes, conglomerado, selviv, hogar, persona
FROM marts.epen_pet
WHERE ocupado AND ingreso_total IS NULL
