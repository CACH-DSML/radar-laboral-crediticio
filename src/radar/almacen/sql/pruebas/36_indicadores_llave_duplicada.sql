-- Una celda por año, desagregación, grupo e indicador.
SELECT anio, desagregacion, ccdd, rama_inei, ciiu_seccion, ocupacion_gran_grupo, indicador
FROM marts.indicadores
GROUP BY ALL
HAVING count(*) > 1
