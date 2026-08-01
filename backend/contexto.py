# -*- coding: utf-8 -*-
"""Puente de solo lectura hacia las estadisticas procesadas del proyecto."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIRECTORIO_DATOS = RAIZ_PROYECTO / "datos"
if str(DIRECTORIO_DATOS) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_DATOS))

from datos_trata import contexto_para_aviso, ficha_nacional, top_departamentos  # noqa: E402


def contexto_local(texto: str) -> dict[str, Any]:
    contexto = contexto_para_aviso(texto)
    return {
        "departamentos_mencionados": contexto["lugares_mencionados"],
        "frases": contexto["frases"],
        "fuente": contexto["nacional"]["fuente"],
    }


def estadisticas_publicas() -> dict[str, Any]:
    return {
        "ficha_nacional": ficha_nacional(),
        "top_departamentos": top_departamentos(10),
    }


if __name__ == "__main__":
    ejemplo = "Trabajo con traslado desde Juliaca hasta Puerto Maldonado."
    print(contexto_local(ejemplo))
    print(estadisticas_publicas())
