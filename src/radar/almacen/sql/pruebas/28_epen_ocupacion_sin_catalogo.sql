-- Todo código de ocupación usado debe estar en el catálogo, con su gran grupo.
SELECT DISTINCT anio, ocupacion
FROM marts.epen_pet
WHERE ocupado AND (ocupacion_nombre IS NULL OR ocupacion_gran_grupo_nombre IS NULL)
