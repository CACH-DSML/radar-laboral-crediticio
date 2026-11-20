-- Catálogo de actividades económicas (C309_COD): clases de la CIIU Revisión 4.
-- Las clases y su descripción salen de las etiquetas de valor de los .dta (año más
-- reciente). La división, el grupo y la sección salen de la estructura oficial de la CIIU.
CREATE OR REPLACE TABLE staging.dim_actividad AS
WITH etiquetas AS (
    SELECT
        lpad(CAST(CAST(codigo AS INTEGER) AS VARCHAR), 4, '0') AS ciiu_clase,
        regexp_replace(trim(arg_max(etiqueta, anio)), '\s+', ' ', 'g') AS descripcion_epen
    FROM raw.epen_etiquetas
    WHERE upper(variable) = 'C309_COD'
    GROUP BY 1
)
SELECT
    e.ciiu_clase,
    e.descripcion_epen,
    clase.descripcion AS descripcion_ciiu,
    left(e.ciiu_clase, 3) AS ciiu_grupo,
    grupo.descripcion AS grupo_nombre,
    left(e.ciiu_clase, 2) AS ciiu_division,
    division.descripcion AS division_nombre,
    division.seccion AS ciiu_seccion,
    seccion.descripcion AS seccion_nombre,
    -- Las cinco ramas con que el INEI publica la población ocupada. La agrupación se
    -- verificó contra el cuadro 1.10A del informe técnico de febrero de 2026.
    CASE
        WHEN division.seccion IN ('A', 'B') THEN 'Agricultura, pesca y minería'
        WHEN division.seccion = 'C' THEN 'Manufactura'
        WHEN division.seccion = 'F' THEN 'Construcción'
        WHEN division.seccion = 'G' THEN 'Comercio'
        WHEN division.seccion IS NOT NULL THEN 'Servicios'
    END AS rama_inei
FROM etiquetas AS e
LEFT JOIN staging.ciiu_rev4 AS division
    ON division.nivel = 'division' AND division.codigo = left(e.ciiu_clase, 2)
LEFT JOIN staging.ciiu_rev4 AS seccion
    ON seccion.nivel = 'seccion' AND seccion.codigo = division.seccion
LEFT JOIN staging.ciiu_rev4 AS grupo
    ON grupo.nivel = 'grupo' AND grupo.codigo = left(e.ciiu_clase, 3)
LEFT JOIN staging.ciiu_rev4 AS clase
    ON clase.nivel = 'clase' AND clase.codigo = e.ciiu_clase;
