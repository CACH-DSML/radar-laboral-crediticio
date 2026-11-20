"""Descarga de archivos con reintentos y registro de procedencia."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

AGENTE = "radar-laboral-crediticio/0.0.1 (proyecto academico)"
NOMBRE_MANIFIESTO = "manifiesto.json"


def descargar(
    url: str, destino: Path, *, reintentos: int = 3, espera: float = 2.0, timeout: float = 60
) -> dict:
    """Guarda el contenido de `url` en `destino` sin modificarlo.

    Devuelve la procedencia del archivo: URL, tamaño, hash y fecha de descarga.
    """
    for intento in range(1, reintentos + 1):
        try:
            peticion = Request(url, headers={"User-Agent": AGENTE})
            with urlopen(peticion, timeout=timeout) as respuesta:
                contenido = respuesta.read()
            break
        except (URLError, TimeoutError) as error:
            if intento == reintentos:
                raise RuntimeError(f"No se pudo descargar {url}: {error}") from error
            time.sleep(espera * intento)

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    return {
        "url": url,
        "bytes": len(contenido),
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "descargado_en": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def guardar_manifiesto(dir_raw: Path, entradas: dict[str, dict]) -> Path:
    """Escribe la procedencia de cada archivo crudo, con rutas relativas a `dir_raw`."""
    ruta = dir_raw / NOMBRE_MANIFIESTO
    ruta.write_text(json.dumps(entradas, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta
