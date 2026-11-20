-- Puestos de trabajo, ingreso promedio y masa salarial del sector formal (nacional).
-- Fuente declarada por el BCRP: Sunat (planilla electrónica).
CREATE OR REPLACE TABLE staging.bcrp_empleo_formal AS
WITH indicadores (codigo, indicador) AS (
    VALUES
        ('PN31879GM', 'puestos_total_miles'),
        ('PN31880GM', 'puestos_total_var12m'),
        ('PN31881GM', 'puestos_privado_miles'),
        ('PN31882GM', 'puestos_privado_var12m'),
        ('PN31883GM', 'ingreso_promedio_soles'),
        ('PN31884GM', 'ingreso_promedio_var12m'),
        ('PN31885GM', 'masa_salarial_millones'),
        ('PN31886GM', 'masa_salarial_var12m')
)
SELECT
    o.fecha,
    o.codigo,
    i.indicador,
    o.nombre_serie,
    o.valor
FROM staging.bcrp_observaciones AS o
LEFT JOIN indicadores AS i USING (codigo)
WHERE o.grupo = 'empleo_formal';
