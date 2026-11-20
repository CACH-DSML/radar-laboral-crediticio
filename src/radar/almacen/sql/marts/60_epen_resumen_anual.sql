-- Totales expandidos de control por año y ámbito (nacional, urbana, rural).
-- Son estimaciones puntuales para validar la ingesta contra las cifras del INEI. No
-- traen error estándar: los indicadores con diseño muestral están en marts.indicadores.
-- Definiciones, verificadas contra los cuadros del INEI:
--   PEA = ocupados + desempleo abierto. El desempleo oculto cuenta como No PEA.
--   El ingreso promedio se calcula entre ocupados con ingreso mayor que cero.
CREATE OR REPLACE TABLE marts.epen_resumen_anual AS
WITH base AS (
    SELECT anio, 'nacional' AS ambito, * EXCLUDE (anio) FROM marts.epen_pet WHERE tiene_factor
    UNION ALL
    SELECT anio, lower(area_nombre) AS ambito, * EXCLUDE (anio)
    FROM marts.epen_pet
    WHERE tiene_factor
)
SELECT
    anio,
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
GROUP BY anio, ambito;
