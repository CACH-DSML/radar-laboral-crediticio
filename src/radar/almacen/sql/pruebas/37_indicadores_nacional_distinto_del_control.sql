-- El nivel nacional de cada indicador debe coincidir con los totales de control, que
-- ya están validados contra el INEI. Compara solo las celdas publicadas.
WITH control AS (
    SELECT anio, 'ocupados' AS indicador, 1000 * ocupados_miles AS valor
    FROM marts.epen_resumen_anual WHERE ambito = 'nacional'
    UNION ALL
    SELECT anio, 'tasa_informalidad', tasa_informalidad
    FROM marts.epen_resumen_anual WHERE ambito = 'nacional'
    UNION ALL
    SELECT anio, 'tasa_afiliacion_pension', tasa_afiliacion_pension
    FROM marts.epen_resumen_anual WHERE ambito = 'nacional'
    UNION ALL
    SELECT anio, 'ingreso_promedio', ingreso_promedio_soles
    FROM marts.epen_resumen_anual WHERE ambito = 'nacional'
)
SELECT i.anio, i.indicador, i.valor, c.valor AS valor_de_control
FROM marts.indicadores AS i
INNER JOIN control AS c
    ON i.anio = c.anio AND i.indicador = c.indicador
WHERE i.desagregacion = 'nacional'
    AND i.valor IS NOT NULL
    AND abs(i.valor - c.valor) > 1e-9 * abs(c.valor)
