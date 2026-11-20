-- Empleo formal nacional por mes, una columna por indicador.
CREATE OR REPLACE TABLE marts.empleo_formal_mensual AS
SELECT
    fecha,
    max(valor) FILTER (WHERE indicador = 'puestos_total_miles') AS puestos_total_miles,
    max(valor) FILTER (WHERE indicador = 'puestos_total_var12m') AS puestos_total_var12m,
    max(valor) FILTER (WHERE indicador = 'puestos_privado_miles') AS puestos_privado_miles,
    max(valor) FILTER (WHERE indicador = 'puestos_privado_var12m') AS puestos_privado_var12m,
    max(valor) FILTER (WHERE indicador = 'ingreso_promedio_soles') AS ingreso_promedio_soles,
    max(valor) FILTER (WHERE indicador = 'ingreso_promedio_var12m') AS ingreso_promedio_var12m,
    max(valor) FILTER (WHERE indicador = 'masa_salarial_millones') AS masa_salarial_millones,
    max(valor) FILTER (WHERE indicador = 'masa_salarial_var12m') AS masa_salarial_var12m
FROM staging.bcrp_empleo_formal
GROUP BY fecha;
