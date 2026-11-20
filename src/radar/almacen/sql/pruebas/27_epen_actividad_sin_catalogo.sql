-- Todo código de actividad usado debe estar en el catálogo, con división y sección.
SELECT DISTINCT anio, ciiu_clase
FROM marts.epen_pet
WHERE ocupado AND (actividad_nombre IS NULL OR ciiu_seccion IS NULL OR seccion_nombre IS NULL)
