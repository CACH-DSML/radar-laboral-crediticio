-- Informal_P con valor en personas que no están ocupadas. El almacén lo ignora.
SELECT anio, mes, conglomerado, ocup300, informal_p
FROM staging.epen_personas
WHERE informal_p IS NOT NULL AND (ocup300 IS NULL OR ocup300 <> 1)
