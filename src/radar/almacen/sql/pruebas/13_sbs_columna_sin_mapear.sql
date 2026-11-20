-- Toda columna del cuadro de la SBS, salvo el exterior, debe ser un departamento conocido.
SELECT DISTINCT columna
FROM staging.sbs_creditos_departamento
WHERE NOT es_exterior AND ccdd IS NULL
