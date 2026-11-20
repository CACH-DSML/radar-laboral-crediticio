-- Población en edad de trabajar (14 años y más) de la EPEN: una fila por persona y visita.
-- Es la base de análisis de las fases 2 y 3. Incluye toda persona con condición de
-- actividad (OCUP300). Las que no tienen factor de expansión quedan marcadas con
-- `tiene_factor = false`: no entran en ninguna estimación expandida.
-- Entre paréntesis, la variable original del INEI.
CREATE OR REPLACE TABLE marts.epen_pet AS
SELECT
    -- Identificación
    p.anio,
    p.mes,
    CAST(ceil(p.mes / 3.0) AS INTEGER) AS trimestre,
    p.llave_panel,                                     -- persona en el panel (LLAVE_PANEL)
    p.muestra,
    p.selviv,
    p.hogar,
    p.c201 AS persona,
    -- Diseño muestral
    p.conglomerado,                                    -- unidad primaria de muestreo
    p.estrato,                                         -- (ESTRATO) tamaño poblacional
    p.ccdd,
    d.departamento,
    p.area,
    CASE p.area WHEN 1 THEN 'Urbana' WHEN 2 THEN 'Rural' END AS area_nombre,
    p.division_lima,
    p.fac300_anual AS factor,                          -- (FAC300_ANUAL)
    p.fac300_anual IS NOT NULL AS tiene_factor,
    -- Persona
    CASE p.c207 WHEN 1 THEN 'Hombre' WHEN 2 THEN 'Mujer' END AS sexo,
    p.c208 AS edad,
    p.c366 AS nivel_educativo,
    -- Condición de actividad (OCUP300)
    p.ocup300 AS condicion_actividad,
    p.ocup300 = 1 AS ocupado,
    p.ocup300 = 2 AS desocupado,                       -- desempleo abierto
    p.ocup300 IN (1, 2) AS pea,
    -- Ocupación principal; solo ocupados
    CASE WHEN p.ocup300 = 1 THEN p.informal_p = 1 END AS informal,       -- (Informal_P)
    CASE WHEN p.ocup300 = 1 THEN p.c308_cod END AS ocupacion,            -- (C308_COD)
    CASE WHEN p.ocup300 = 1 THEN o.descripcion END AS ocupacion_nombre,
    CASE WHEN p.ocup300 = 1 THEN o.gran_grupo END AS ocupacion_gran_grupo,
    CASE WHEN p.ocup300 = 1 THEN o.gran_grupo_nombre END AS ocupacion_gran_grupo_nombre,
    CASE WHEN p.ocup300 = 1 THEN p.c309_cod END AS ciiu_clase,           -- (C309_COD)
    CASE WHEN p.ocup300 = 1 THEN a.descripcion_epen END AS actividad_nombre,
    CASE WHEN p.ocup300 = 1 THEN a.ciiu_division END AS ciiu_division,
    CASE WHEN p.ocup300 = 1 THEN a.division_nombre END AS division_nombre,
    CASE WHEN p.ocup300 = 1 THEN a.ciiu_seccion END AS ciiu_seccion,
    CASE WHEN p.ocup300 = 1 THEN a.seccion_nombre END AS seccion_nombre,
    CASE WHEN p.ocup300 = 1 THEN a.rama_inei END AS rama_inei,
    CASE WHEN p.ocup300 = 1 THEN p.c310 END AS categoria_ocupacional,    -- (C310)
    CASE WHEN p.ocup300 = 1 THEN p.c311 END AS tipo_empleador,           -- (C311)
    CASE WHEN p.ocup300 = 1 THEN p.c312 END AS registro_sunat,           -- (C312)
    CASE WHEN p.ocup300 = 1 THEN p.c317 END AS tamanio_empresa,          -- (C317)
    CASE WHEN p.ocup300 = 1 THEN p.c317a END AS trabajadores_empresa,    -- (C317A)
    CASE WHEN p.ocup300 = 1 THEN p.c338 END AS frecuencia_pago,          -- (C338)
    CASE WHEN p.ocup300 = 1 THEN p.whorat END AS horas_semana,           -- (whoraT)
    CASE WHEN p.ocup300 = 1 THEN p.c331 END AS horas_habituales,         -- (C331)
    CASE WHEN p.ocup300 = 1 THEN p.p209h = 1 END AS quiere_mas_horas,    -- (P209H)
    CASE WHEN p.ocup300 = 1 THEN p.c335 = 1 END AS busca_otro_trabajo,   -- (C335)
    -- Ingreso mensual por trabajo, en soles corrientes; solo ocupados
    CASE WHEN p.ocup300 = 1 THEN p.ingtrabw END AS ingreso_total,        -- (ingtrabw)
    CASE WHEN p.ocup300 = 1 THEN p.ingtot END AS ingreso_sin_extraordinarios,  -- (INGTOT)
    CASE WHEN p.ocup300 = 1 THEN p.ingtotp END AS ingreso_principal,     -- (INGTOTP)
    -- Protección social
    p.seguro1 AS seguro_salud,                                           -- (SEGURO1)
    p.c364_1 = 1 OR p.c364_2 = 1 OR p.c364_3 = 1 OR p.c364_4 = 1 AS afiliado_pension,
    -- Desocupados e inactivos
    p.c358 AS semanas_buscando,                                          -- (C358)
    p.c359 = 1 AS trabajo_antes                                          -- (C359)
FROM staging.epen_personas AS p
LEFT JOIN staging.dim_departamento AS d
    ON p.ccdd = d.ccdd
LEFT JOIN staging.dim_ocupacion AS o
    ON p.c308_cod = o.ocupacion
LEFT JOIN staging.dim_actividad AS a
    ON p.c309_cod = a.ciiu_clase
WHERE p.ocup300 IS NOT NULL;
