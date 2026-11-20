-- Todo ocupado tiene ocupación, actividad y situación de informalidad.
SELECT anio, mes, conglomerado, ocupacion, ciiu_clase, informal
FROM marts.epen_pet
WHERE ocupado AND (ocupacion IS NULL OR ciiu_clase IS NULL OR informal IS NULL)
