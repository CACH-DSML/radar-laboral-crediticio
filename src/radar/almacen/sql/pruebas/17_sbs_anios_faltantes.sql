-- Deben estar los cuatro cortes de diciembre que cubre la EPEN.
SELECT esperado.anio
FROM (VALUES (2022), (2023), (2024), (2025)) AS esperado (anio)
WHERE esperado.anio NOT IN (SELECT anio FROM marts.sbs_banca_departamento_anual)
