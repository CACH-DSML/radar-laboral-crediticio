-- El crédito total de cada departamento y mes debe existir y ser positivo.
SELECT * FROM marts.credito_departamento_mensual
WHERE credito_total_millones IS NULL OR credito_total_millones <= 0
