-- Compara cada cifra trimestral oficial del INEI con el total expandido del almacén.
CREATE OR REPLACE TABLE marts.epen_validacion_trimestral AS
WITH estimado AS (
    UNPIVOT (
        SELECT * EXCLUDE (personas_muestra, fecha)
        FROM marts.epen_resumen_trimestral
    )
    ON COLUMNS (* EXCLUDE (anio, trimestre, ambito))
    INTO NAME indicador VALUE valor
)
SELECT
    CAST(o.anio AS INTEGER) AS anio,
    CAST(o.trimestre AS INTEGER) AS trimestre,
    o.ambito,
    o.indicador,
    CAST(o.valor AS DOUBLE) AS valor_oficial,
    e.valor AS valor_estimado,
    e.valor - CAST(o.valor AS DOUBLE) AS diferencia,
    CAST(o.tolerancia AS DOUBLE) AS tolerancia,
    coalesce(abs(e.valor - CAST(o.valor AS DOUBLE)) <= CAST(o.tolerancia AS DOUBLE), false)
        AS coincide,
    o.fuente
FROM staging.epen_cifras_oficiales_trimestrales AS o
LEFT JOIN estimado AS e
    ON CAST(o.anio AS INTEGER) = e.anio
    AND CAST(o.trimestre AS INTEGER) = e.trimestre
    AND o.ambito = e.ambito
    AND o.indicador = e.indicador;
