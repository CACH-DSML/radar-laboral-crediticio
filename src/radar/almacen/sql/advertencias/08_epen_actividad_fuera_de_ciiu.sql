-- Clases de actividad de la EPEN que no existen como clase en la CIIU Revisión 4 oficial.
SELECT ciiu_clase, descripcion_epen
FROM staging.dim_actividad
WHERE descripcion_ciiu IS NULL
