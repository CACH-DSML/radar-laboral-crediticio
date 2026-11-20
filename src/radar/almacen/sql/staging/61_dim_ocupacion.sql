-- Catálogo de ocupaciones (C308_COD): grupos primarios del Clasificador Nacional de
-- Ocupaciones 2015. Los códigos y su descripción salen de las etiquetas de valor de los
-- .dta (año más reciente). El gran grupo es el primer dígito del código.
CREATE OR REPLACE TABLE staging.dim_ocupacion AS
WITH etiquetas AS (
    SELECT
        lpad(CAST(CAST(codigo AS INTEGER) AS VARCHAR), 4, '0') AS ocupacion,
        regexp_replace(trim(arg_max(etiqueta, anio)), '\s+', ' ', 'g') AS descripcion
    FROM raw.epen_etiquetas
    WHERE upper(variable) = 'C308_COD'
    GROUP BY 1
)
SELECT
    e.ocupacion,
    e.descripcion,
    left(e.ocupacion, 3) AS subgrupo,
    left(e.ocupacion, 2) AS subgrupo_principal,
    left(e.ocupacion, 1) AS gran_grupo,
    g.descripcion AS gran_grupo_nombre
FROM etiquetas AS e
LEFT JOIN staging.cno_grandes_grupos AS g
    ON g.gran_grupo = left(e.ocupacion, 1);
