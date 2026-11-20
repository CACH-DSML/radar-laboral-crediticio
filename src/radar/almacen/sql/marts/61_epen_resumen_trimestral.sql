-- Totales expandidos por trimestre calendario y ámbito, con las mismas definiciones que
-- `marts.epen_resumen_anual`.
-- El factor anual reparte la población entre los doce meses del año. Dentro de un
-- trimestre se multiplica por 4 para llevarlo a nivel de población. Con esa regla se
-- reproducen las cifras trimestrales del INEI (ver `marts.epen_validacion_trimestral`).
-- Son estimaciones puntuales, sin error estándar.
CREATE OR REPLACE TABLE marts.epen_resumen_trimestral AS
WITH pet AS (
    SELECT * REPLACE (4 * factor AS factor) FROM marts.epen_pet WHERE tiene_factor
),
base AS (
    SELECT anio, trimestre, 'nacional' AS ambito, * EXCLUDE (anio, trimestre) FROM pet
    UNION ALL
    SELECT anio, trimestre, lower(area_nombre) AS ambito, * EXCLUDE (anio, trimestre) FROM pet
)
SELECT
    anio,
    trimestre,
    make_date(anio, 3 * trimestre - 2, 1) AS fecha,
    ambito,
    count(*) AS personas_muestra,
    sum(factor) / 1000 AS pet_miles,
    sum(factor) FILTER (WHERE pea) / 1000 AS pea_miles,
    sum(factor) FILTER (WHERE NOT pea) / 1000 AS no_pea_miles,
    sum(factor) FILTER (WHERE ocupado) / 1000 AS ocupados_miles,
    sum(factor) FILTER (WHERE desocupado) / 1000 AS desocupados_miles,
    100 * sum(factor) FILTER (WHERE pea) / sum(factor) AS tasa_actividad,
    100 * sum(factor) FILTER (WHERE desocupado) / sum(factor) FILTER (WHERE pea)
        AS tasa_desempleo,
    100 * sum(factor) FILTER (WHERE informal) / sum(factor) FILTER (WHERE ocupado)
        AS tasa_informalidad,
    sum(factor * ingreso_total) FILTER (WHERE ingreso_total > 0)
    / sum(factor) FILTER (WHERE ingreso_total > 0) AS ingreso_promedio_soles,
    100 * sum(factor) FILTER (WHERE ocupado AND afiliado_pension)
    / sum(factor) FILTER (WHERE ocupado) AS tasa_afiliacion_pension,
    sum(factor) FILTER (WHERE rama_inei = 'Agricultura, pesca y minería') / 1000
        AS ocupados_agro_pesca_mineria_miles,
    sum(factor) FILTER (WHERE rama_inei = 'Manufactura') / 1000 AS ocupados_manufactura_miles,
    sum(factor) FILTER (WHERE rama_inei = 'Construcción') / 1000 AS ocupados_construccion_miles,
    sum(factor) FILTER (WHERE rama_inei = 'Comercio') / 1000 AS ocupados_comercio_miles,
    sum(factor) FILTER (WHERE rama_inei = 'Servicios') / 1000 AS ocupados_servicios_miles
FROM base
GROUP BY anio, trimestre, ambito;
