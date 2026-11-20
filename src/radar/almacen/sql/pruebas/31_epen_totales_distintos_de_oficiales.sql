-- Los totales expandidos deben reproducir las cifras publicadas por el INEI.
SELECT anio, ambito, indicador, valor_oficial, valor_estimado, diferencia
FROM marts.epen_validacion_oficial
WHERE NOT coincide
