-- Puestos, ingreso y masa salarial deben existir y ser positivos en todos los meses.
SELECT * FROM marts.empleo_formal_mensual
WHERE coalesce(puestos_total_miles, 0) <= 0
    OR coalesce(puestos_privado_miles, 0) <= 0
    OR coalesce(ingreso_promedio_soles, 0) <= 0
    OR coalesce(masa_salarial_millones, 0) <= 0
