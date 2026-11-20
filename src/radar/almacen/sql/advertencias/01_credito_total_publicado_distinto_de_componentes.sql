-- Meses en que el total publicado por el BCRP difiere de moneda nacional más extranjera
-- en más de 0.01%. Es una anomalía de la fuente: se informa, no detiene el pipeline.
SELECT fecha, ccdd, credito_total_millones, credito_total_publicado_millones
FROM marts.credito_departamento_mensual
WHERE total_publicado_inconsistente
