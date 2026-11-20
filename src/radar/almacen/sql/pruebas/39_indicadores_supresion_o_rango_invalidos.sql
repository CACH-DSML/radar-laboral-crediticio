-- Una celda suprimida no muestra valor; una publicada sí. Las tasas van de 0 a 100,
-- ningún valor es negativo y ningún ocupado queda sin clasificar.
SELECT anio, desagregacion, indicador, calidad, valor, ee
FROM marts.indicadores
WHERE (calidad = 'suprimida' AND (valor IS NOT NULL OR ee IS NOT NULL))
    OR '(sin clasificar)' IN (ccdd, rama_inei, ciiu_seccion, ocupacion_gran_grupo)
    OR (calidad <> 'suprimida' AND valor IS NULL)
    OR calidad NOT IN ('publicable', 'referencial', 'suprimida')
    OR valor < 0
    OR (unidad = 'porcentaje' AND valor > 100)
    OR n < 1
