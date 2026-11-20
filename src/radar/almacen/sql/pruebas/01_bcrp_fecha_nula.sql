-- Todo periodo del BCRP debe convertirse a fecha.
SELECT * FROM staging.bcrp_observaciones WHERE fecha IS NULL
