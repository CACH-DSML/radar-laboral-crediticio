-- Los ingresos por trabajo no pueden ser negativos.
SELECT anio, mes, conglomerado, ingreso_total, ingreso_principal
FROM marts.epen_pet
WHERE ingreso_total < 0 OR ingreso_principal < 0 OR ingreso_sin_extraordinarios < 0
