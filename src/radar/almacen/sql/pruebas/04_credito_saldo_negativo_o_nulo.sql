-- Los saldos de crédito no pueden faltar ni ser negativos.
SELECT * FROM staging.bcrp_credito_departamento
WHERE saldo_millones IS NULL OR saldo_millones < 0
