-- Resumen anual del crédito por departamento, para cruzar con la EPEN anual.
-- 'meses' indica cuántos meses del año tienen dato; un año en curso tendrá menos de 12.
CREATE OR REPLACE TABLE marts.credito_departamento_anual AS
SELECT
    year(fecha) AS anio,
    ccdd,
    departamento,
    count(*) AS meses,
    avg(credito_total_millones) AS credito_promedio_millones,
    any_value(credito_total_millones) FILTER (WHERE month(fecha) = 12) AS credito_diciembre_millones,
    any_value(dolarizacion) FILTER (WHERE month(fecha) = 12) AS dolarizacion_diciembre,
    any_value(var_12m) FILTER (WHERE month(fecha) = 12) AS var_12m_diciembre
FROM marts.credito_departamento_mensual
GROUP BY year(fecha), ccdd, departamento;
