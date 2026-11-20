-- Base de modelado: una fila por persona, con su primera visita como
-- ocupada con ingreso (origen) y su situación 12 meses después (destino).
--
-- Reglas:
--   * Una sola fila por persona: la primera visita de origen. Así nadie aparece en dos
--     cohortes y la partición temporal no mezcla a la misma persona.
--   * El par se descarta si la llave no es coherente: sexo distinto, o una edad que no
--     avanza entre 0 y 2 años.
--   * Todas las columnas sin sufijo son del origen. Las del destino terminan en
--     `_destino` y solo sirven para construir los eventos: nunca son predictores.
CREATE OR REPLACE TABLE marts.panel_12m AS
WITH pares AS (
    SELECT
        o.llave_panel,
        o.anio AS anio_origen,
        o.mes AS mes_origen,
        o.trimestre,
        o.conglomerado,
        o.estrato,
        o.ccdd,
        o.departamento,
        o.area_nombre,
        o.factor,
        o.sexo,
        o.edad,
        o.nivel_educativo,
        o.informal,
        o.ocupacion_gran_grupo,
        o.ciiu_seccion,
        o.rama_inei,
        o.categoria_ocupacional,
        o.tipo_empleador,
        o.registro_sunat,
        o.tamanio_empresa,
        o.trabajadores_empresa,
        o.frecuencia_pago,
        o.horas_semana,
        o.quiere_mas_horas,
        o.busca_otro_trabajo,
        o.seguro_salud,
        o.afiliado_pension,
        o.ingreso_total,
        d.ocupado AS ocupado_destino,
        d.condicion_actividad AS condicion_destino,
        d.informal AS informal_destino,
        d.ingreso_total AS ingreso_destino,
        row_number() OVER (PARTITION BY o.llave_panel ORDER BY o.anio, o.mes) AS orden
    FROM marts.epen_pet AS o
    INNER JOIN marts.epen_pet AS d
        ON o.llave_panel = d.llave_panel
        AND (d.anio - o.anio) * 12 + (d.mes - o.mes) = 12
    WHERE o.ocupado
        AND o.ingreso_total > 0
        AND o.sexo = d.sexo
        AND d.edad - o.edad BETWEEN 0 AND 2
        -- un ocupado en el destino debe tener dato de ingreso para medir la caída
        AND (NOT d.ocupado OR d.ingreso_total IS NOT NULL)
)
SELECT
    * EXCLUDE (orden),
    -- Evento principal: deja de estar ocupada, o su ingreso nominal cae 30% o más.
    NOT ocupado_destino OR ingreso_destino < 0.7 * ingreso_total AS pierde_ingreso_30,
    -- Sensibilidad: la misma definición con una caída de 50% o más.
    NOT ocupado_destino OR ingreso_destino < 0.5 * ingreso_total AS pierde_ingreso_50,
    -- Contraste: solo la pérdida del empleo, que no depende del ingreso declarado.
    NOT ocupado_destino AS pierde_empleo
FROM pares
WHERE orden = 1;
