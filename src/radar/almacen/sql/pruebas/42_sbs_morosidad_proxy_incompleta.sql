-- Todo banco con colocaciones en un departamento debe tener su morosidad, la cifra debe
-- existir y ser un porcentaje, y cada año debe traer los 24 departamentos.
SELECT 'banco sin morosidad o cifra inválida' AS problema, CAST(anio AS VARCHAR) || '-' || ccdd AS detalle
FROM marts.sbs_morosidad_proxy_departamento
WHERE bancos_sin_morosidad > 0
    OR morosidad_proxy_pct IS NULL
    OR morosidad_proxy_pct NOT BETWEEN 0 AND 100
UNION ALL
SELECT 'año sin 24 departamentos', CAST(anio AS VARCHAR)
FROM marts.sbs_morosidad_proxy_departamento
GROUP BY anio
HAVING count(*) <> 24
