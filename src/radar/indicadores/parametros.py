"""Parámetros de estimación decididos por el autor."""

from __future__ import annotations

from radar.indicadores.estimacion import Diseno
from radar.indicadores.supresion import ReglaSupresion

# El estrato es el cruce de departamento y estrato poblacional. El único
# estrato con un solo conglomerado (Ucayali, estrato 6) se trata como unidad de certeza.
DISENO_EPEN = Diseno(
    peso="factor",
    upm="conglomerado",
    estratos=("ccdd", "estrato"),
    upm_unica="certeza",
)

# El de los do-files originales: `svyset ..., strata(ESTRATO)`. Se conserva para comparar.
DISENO_DOFILES = Diseno(peso="factor", upm="conglomerado", estratos=("estrato",))

# Se suprime con menos de 30 casos o menos de 2 conglomerados; la celda es
# referencial desde 15% de coeficiente de variación y se suprime desde 30%.
REGLA_EPEN = ReglaSupresion(n_minimo=30, upm_minimas=2, cv_referencial=0.15, cv_maximo=0.30)
