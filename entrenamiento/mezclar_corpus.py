# -*- coding: utf-8 -*-
"""Ensambla corpus.jsonl a partir de las tres fuentes de entrenamiento.

  corpus-sintetico.jsonl   generado aqui; distribucion de señales derivada de
                           3 822 denuncias PNP 2017-2023 (ver generar_corpus.py)
  avisos-reales.jsonl      25 avisos publicados reales, anonimizados y con URL
  avisos-externos.jsonl    15 sinteticos redactados por otro modelo; aportan
                           diversidad de redaccion contra el sobreajuste

Cada ejemplo conserva su campo 'origen' para trazabilidad en el repositorio
publico: cualquiera puede auditar de donde salio cada linea del corpus.
El entrenamiento solo lee 'messages', asi que los campos extra no estorban.

Uso: python mezclar_corpus.py
"""
import json
import random
import re

from normalizar_catalogo import normalizar_respuesta
from validar_pii import REEMPLAZOS

random.seed(20260801)

FUENTES = [
    {
        "ruta": "corpus-sintetico.jsonl",
        "origen": "sintetico-propio",
        "tipo": "sintetico",
        "fuente": "Generador local reproducible generar_corpus.py",
    },
    {
        "ruta": "avisos-reales.jsonl",
        "origen": "real-publicado",
        "tipo": "real anonimizado",
        "fuente": "Conservada desde avisos-reales.jsonl",
    },
    {
        "ruta": "avisos-externos.jsonl",
        "origen": "sintetico-externo",
        "tipo": "sintetico",
        "fuente": "Ejemplos sinteticos redactados para diversidad",
    },
]
SALIDA = "corpus.jsonl"


def normaliza(t):
    return re.sub(r"\s+", " ", t.strip().lower())


def anonimizar_mensajes(ejemplo):
    for mensaje in ejemplo.get("messages", []):
        texto = mensaje.get("content", "")
        for patron, reemplazo in REEMPLAZOS:
            texto = patron.sub(reemplazo, texto)
        mensaje["content"] = texto


def main():
    todos, vistos, resumen = [], set(), {}

    for metadatos in FUENTES:
        ruta = metadatos["ruta"]
        origen = metadatos["origen"]
        try:
            lineas = [l for l in open(ruta, encoding="utf-8") if l.strip()]
        except FileNotFoundError:
            print("FALTA %s -- se omite" % ruta)
            continue

        aceptados, repetidos = 0, 0
        for linea in lineas:
            ej = json.loads(linea)
            clave = normaliza(ej["messages"][0]["content"])[:100]
            if clave in vistos:
                repetidos += 1
                continue
            vistos.add(clave)
            anonimizar_mensajes(ej)
            ej["messages"][1]["content"] = normalizar_respuesta(
                ej["messages"][1]["content"]
            )
            ej["origen"] = ej.get("origen") or origen
            ej["tipo"] = ej.get("tipo") or metadatos["tipo"]
            if not ej.get("fuente"):
                ej["fuente"] = metadatos["fuente"]
            todos.append(ej)
            aceptados += 1

        conteo = {}
        for ej in todos[-aceptados:] if aceptados else []:
            n = ej["messages"][1]["content"].split("\n")[0].replace("RIESGO: ", "")
            conteo[n] = conteo.get(n, 0) + 1
        resumen[origen] = (aceptados, repetidos, conteo)

    random.shuffle(todos)
    with open(SALIDA, "w", encoding="utf-8") as f:
        for ej in todos:
            f.write(json.dumps(ej, ensure_ascii=False) + "\n")

    print("Fuentes:")
    for origen, (n, rep, conteo) in resumen.items():
        detalle = "  ".join("%s %d" % (k, conteo.get(k, 0)) for k in ("alto", "medio", "bajo"))
        extra = "  (%d descartados por duplicado)" % rep if rep else ""
        print("  %-18s %3d ejemplos   %s%s" % (origen, n, detalle, extra))

    total = {}
    for ej in todos:
        n = ej["messages"][1]["content"].split("\n")[0].replace("RIESGO: ", "")
        total[n] = total.get(n, 0) + 1
    print("\n%s: %d ejemplos" % (SALIDA, len(todos)))
    for k in ("alto", "medio", "bajo"):
        print("  %-6s %3d  (%.1f%%)" % (k, total.get(k, 0), 100.0 * total.get(k, 0) / len(todos)))


if __name__ == "__main__":
    main()
