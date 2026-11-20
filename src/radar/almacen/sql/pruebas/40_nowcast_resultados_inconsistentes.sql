-- El error es pronóstico menos real, hay un pronóstico por modelo y trimestre, y el
-- baseline se compara consigo mismo con razón 1.
SELECT 'error mal calculado' AS problema, objetivo, modelo, CAST(fecha AS VARCHAR) AS detalle
FROM marts.nowcast_evaluacion
WHERE abs(error - (pronostico - real)) > 1e-9 * greatest(abs(real), 1)
UNION ALL
SELECT 'pronóstico duplicado', objetivo, modelo, CAST(fecha AS VARCHAR)
FROM marts.nowcast_evaluacion
GROUP BY objetivo, modelo, fecha
HAVING count(*) > 1
UNION ALL
SELECT 'baseline con razón distinta de 1', objetivo, modelo, CAST(relativo_al_baseline AS VARCHAR)
FROM marts.nowcast_resumen
WHERE modelo = 'ingenuo' AND abs(relativo_al_baseline - 1) > 1e-12
