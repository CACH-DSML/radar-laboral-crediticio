-- En la base de modelado cada persona aparece una vez, el origen es un ocupado con
-- ingreso, y los eventos son coherentes entre sí: quien pierde el empleo también cuenta
-- como pérdida de ingreso, y una caída de 50% implica una de 30%.
SELECT 'persona duplicada' AS problema, llave_panel
FROM marts.panel_12m
GROUP BY llave_panel
HAVING count(*) > 1
UNION ALL
SELECT 'origen o eventos incoherentes', llave_panel
FROM marts.panel_12m
WHERE ingreso_total IS NULL OR ingreso_total <= 0
    OR pierde_ingreso_30 IS NULL OR pierde_ingreso_50 IS NULL OR pierde_empleo IS NULL
    OR (pierde_empleo AND NOT pierde_ingreso_50)
    OR (pierde_ingreso_50 AND NOT pierde_ingreso_30)
