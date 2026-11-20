-- Los puntajes y las métricas del modelo están en su rango, y hay una fila por celda.
SELECT 'score fuera de rango o sin muestra' AS problema, desagregacion AS detalle
FROM marts.score_segmento
WHERE (calidad <> 'suprimida' AND (score IS NULL OR score NOT BETWEEN 0 AND 100)) OR n < 1
UNION ALL
SELECT 'celda de score duplicada', desagregacion
FROM marts.score_segmento
GROUP BY anio, objetivo, desagregacion, ccdd, rama_inei, ocupacion_gran_grupo
HAVING count(*) > 1
UNION ALL
SELECT 'métrica fuera de rango', objetivo || ' ' || modelo || ' ' || parte
FROM marts.modelo_metricas
WHERE auc NOT BETWEEN 0 AND 1 OR ks NOT BETWEEN 0 AND 1 OR brier NOT BETWEEN 0 AND 1
