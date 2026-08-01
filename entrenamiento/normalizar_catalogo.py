# -*- coding: utf-8 -*-
"""Normaliza las respuestas de entrenamiento al catalogo contractual.

Por defecto solo informa. Usa --aplicar cuando no haya un entrenamiento activo;
se conserva una copia .antes-catalogo para reproducir el adaptador anterior.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


AQUI = Path(__file__).resolve().parent
BACKEND = AQUI.parent / "backend"
sys.path.insert(0, str(BACKEND))

from extractor import (  # noqa: E402
    BANDERA_MENORES,
    BANDERA_SIN_ALERTAS,
    CATALOGO_POR_GRAVEDAD,
    canonizar_bandera,
    normalizar,
    parsear_salida_modelo,
)


PERMITIDAS = {
    normalizar(bandera): bandera
    for banderas in CATALOGO_POR_GRAVEDAD.values()
    for bandera in banderas
}
PERMITIDAS[normalizar(BANDERA_MENORES)] = BANDERA_MENORES
PERMITIDAS[normalizar(BANDERA_SIN_ALERTAS)] = BANDERA_SIN_ALERTAS


def normalizar_respuesta(texto):
    analisis = parsear_salida_modelo(texto)
    if not analisis["formato_valido"]:
        raise ValueError("respuesta con formato invalido")

    banderas = []
    for bandera in analisis["banderas"]:
        for canonica in canonizar_bandera(bandera):
            exacta = PERMITIDAS.get(normalizar(canonica))
            if not exacta:
                raise ValueError("bandera sin equivalencia: %s" % canonica)
            if exacta not in banderas:
                banderas.append(exacta)

    if analisis["riesgo"] == "bajo":
        banderas = [BANDERA_SIN_ALERTAS]
    else:
        banderas = [b for b in banderas if b != BANDERA_SIN_ALERTAS]
        if not banderas:
            raise ValueError("respuesta no-baja quedaria sin banderas")

    return (
        "RIESGO: %s\nBANDERAS:\n%s\nEXPLICACION: %s"
        % (analisis["riesgo"], "\n".join("- " + b for b in banderas), analisis["explicacion"])
    )


def procesar(ruta, aplicar=False):
    salida, cambios, errores = [], 0, []
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        ejemplo = json.loads(linea)
        original = ejemplo["messages"][1]["content"]
        try:
            normalizada = normalizar_respuesta(original)
        except ValueError as error:
            errores.append("linea %d: %s" % (numero, error))
            continue
        cambios += int(normalizada != original)
        ejemplo["messages"][1]["content"] = normalizada
        salida.append(ejemplo)

    print("%s: %d respuestas por normalizar, %d errores" % (ruta.name, cambios, len(errores)))
    for error in errores[:20]:
        print("  " + error)
    if errores:
        return 1
    if aplicar and cambios:
        respaldo = ruta.with_suffix(ruta.suffix + ".antes-catalogo")
        if not respaldo.exists():
            shutil.copy2(ruta, respaldo)
        contenido = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in salida)
        ruta.write_text(contenido, encoding="utf-8")
        print("  aplicado; respaldo privado: %s" % respaldo.name)
    return int(cambios > 0 and not aplicar)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archivos", nargs="*", default=["corpus.jsonl", "evaluacion.jsonl"])
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    return max(procesar(AQUI / nombre, args.aplicar) for nombre in args.archivos)


if __name__ == "__main__":
    raise SystemExit(main())
