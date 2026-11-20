-- Base del nowcast: una fila por trimestre calendario, a nivel nacional.
-- Junta el empleo de la EPEN (desde 2022) con los indicadores mensuales del BCRP
-- llevados al trimestre (desde 2015). Antes de 2022 las columnas de la EPEN son nulas.
-- `meses_bcrp` dice cuántos meses del trimestre tienen dato: con menos de 3, el
-- trimestre está incompleto y su promedio no es comparable.
CREATE OR REPLACE TABLE marts.nowcast_trimestral AS
WITH bcrp AS (
    SELECT
        date_trunc('quarter', fecha)::DATE AS fecha,
        count(puestos_total_miles) AS meses_bcrp,
        avg(puestos_total_miles) AS puestos_formales_miles,
        avg(puestos_privado_miles) AS puestos_formales_privados_miles,
        avg(ingreso_promedio_soles) AS ingreso_formal_promedio_soles,
        sum(masa_salarial_millones) AS masa_salarial_formal_millones
    FROM marts.empleo_formal_mensual
    GROUP BY 1
),
epen AS (
    SELECT
        fecha,
        personas_muestra,
        pet_miles,
        pea_miles,
        ocupados_miles,
        desocupados_miles,
        tasa_desempleo,
        tasa_informalidad,
        ingreso_promedio_soles
    FROM marts.epen_resumen_trimestral
    WHERE ambito = 'nacional'
)
SELECT
    coalesce(b.fecha, e.fecha) AS fecha,
    year(coalesce(b.fecha, e.fecha)) AS anio,
    quarter(coalesce(b.fecha, e.fecha)) AS trimestre,
    e.personas_muestra,
    e.pet_miles,
    e.pea_miles,
    e.ocupados_miles,
    e.desocupados_miles,
    e.tasa_desempleo,
    e.tasa_informalidad,
    e.ingreso_promedio_soles,
    coalesce(b.meses_bcrp, 0) AS meses_bcrp,
    b.puestos_formales_miles,
    b.puestos_formales_privados_miles,
    b.ingreso_formal_promedio_soles,
    b.masa_salarial_formal_millones
FROM bcrp AS b
FULL OUTER JOIN epen AS e
    ON b.fecha = e.fecha;
