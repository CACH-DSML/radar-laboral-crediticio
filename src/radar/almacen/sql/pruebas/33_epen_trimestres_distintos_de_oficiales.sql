-- Los totales trimestrales deben reproducir las cifras publicadas por el INEI.
SELECT anio, trimestre, ambito, indicador, valor_oficial, valor_estimado, diferencia
FROM marts.epen_validacion_trimestral
WHERE NOT coincide
