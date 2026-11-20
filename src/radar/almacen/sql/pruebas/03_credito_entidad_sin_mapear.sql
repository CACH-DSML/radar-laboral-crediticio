-- Toda serie de crédito debe tener moneda, y todo departamento debe estar en el catálogo.
SELECT DISTINCT codigo, entidad, moneda
FROM staging.bcrp_credito_departamento
WHERE moneda = '' OR (NOT es_total_nacional AND ccdd IS NULL)
