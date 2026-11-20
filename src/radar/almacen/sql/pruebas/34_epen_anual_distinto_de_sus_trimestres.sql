-- Un nivel anual es la cuarta parte de la suma de sus niveles trimestrales. Si no
-- coincide, el resumen anual y el trimestral dejaron de usar la misma definición.
WITH trimestres AS (
    SELECT
        anio,
        ambito,
        sum(pet_miles) / 4 AS pet_miles,
        sum(ocupados_miles) / 4 AS ocupados_miles,
        sum(desocupados_miles) / 4 AS desocupados_miles
    FROM marts.epen_resumen_trimestral
    GROUP BY anio, ambito
)
SELECT a.anio, a.ambito, a.pet_miles, t.pet_miles AS pet_desde_trimestres
FROM marts.epen_resumen_anual AS a
LEFT JOIN trimestres AS t
    ON a.anio = t.anio AND a.ambito = t.ambito
WHERE t.anio IS NULL
    OR abs(a.pet_miles - t.pet_miles) > 1e-6 * a.pet_miles
    OR abs(a.ocupados_miles - t.ocupados_miles) > 1e-6 * a.ocupados_miles
    OR abs(coalesce(a.desocupados_miles, 0) - coalesce(t.desocupados_miles, 0))
    > 1e-6 * a.pet_miles
