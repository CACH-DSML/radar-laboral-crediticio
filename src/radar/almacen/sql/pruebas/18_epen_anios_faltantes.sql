-- Deben estar las cuatro bases anuales de la EPEN.
SELECT esperado.anio
FROM (VALUES (2022), (2023), (2024), (2025)) AS esperado (anio)
WHERE esperado.anio NOT IN (SELECT anio FROM staging.epen_personas)
