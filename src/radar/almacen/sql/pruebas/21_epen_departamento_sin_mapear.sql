-- Todo CCDD de la EPEN debe existir en el catálogo de departamentos de la EPEN.
SELECT DISTINCT p.anio, p.ccdd
FROM staging.epen_personas AS p
WHERE p.ccdd NOT IN (SELECT ccdd_epen FROM staging.dim_departamento)
