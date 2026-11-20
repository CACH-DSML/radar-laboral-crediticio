SELECT DISTINCT codigo, nombre_serie
FROM staging.bcrp_empleo_formal
WHERE indicador IS NULL
