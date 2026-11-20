-- Una fila por serie y mes, con fecha y valor tipados.
-- El BCRP entrega el periodo como 'Oct.2004' y los faltantes como 'n.d.'.
-- Algunos nombres de serie llegan con un espacio al final (Cajamarca, Madre de Dios).
CREATE OR REPLACE TABLE staging.bcrp_observaciones AS
SELECT
    grupo,
    codigo,
    trim(nombre_serie) AS nombre_serie,
    make_date(
        CAST(split_part(periodo, '.', 2) AS INTEGER),
        CASE split_part(periodo, '.', 1)
            WHEN 'Ene' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3 WHEN 'Abr' THEN 4
            WHEN 'May' THEN 5 WHEN 'Jun' THEN 6 WHEN 'Jul' THEN 7 WHEN 'Ago' THEN 8
            WHEN 'Sep' THEN 9 WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dic' THEN 12
        END,
        1
    ) AS fecha,
    TRY_CAST(valor_texto AS DOUBLE) AS valor
FROM raw.bcrp_observaciones;
