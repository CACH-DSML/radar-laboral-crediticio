-- Personas con condición de actividad pero sin factor de expansión anual.
-- No entran en las estimaciones expandidas. El INEI no documenta el motivo.
SELECT anio, mes, conglomerado, selviv, hogar, persona
FROM marts.epen_pet
WHERE NOT tiene_factor
