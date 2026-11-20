-- Personas con factor de expansión igual a cero.
SELECT anio, mes, conglomerado, selviv, hogar, persona
FROM marts.epen_pet
WHERE factor = 0
