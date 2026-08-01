# -*- coding: utf-8 -*-
"""COMPUERTA 1: valida corpus.jsonl y evaluacion.jsonl antes de entrenar.

El 90% de los entrenamientos fallidos mueren por datos, no por hiperparametros.
Bloquean: estructura, formato de salida, etiquetas, duplicados y fuga de datos.
Solo advierten: distribucion de clases y longitud.

Uso: python validar_corpus.py
"""
import json
import os
import re
import sys
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(AQUI, "..", "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from extractor import (  # noqa: E402
    BANDERA_MENORES,
    BANDERA_SIN_ALERTAS,
    CATALOGO_POR_GRAVEDAD,
    normalizar as normalizar_bandera,
    parsear_salida_modelo,
)

MODELO = os.environ.get("MODELO_BASE", "/home/abel_brayan/gemma-4-e2b")
CORPUS = "corpus.jsonl"
EVAL = "evaluacion.jsonl"

FORMATO = re.compile(r"^RIESGO: (bajo|medio|alto)\nBANDERAS:\n(?:- .+\n)+EXPLICACION: .+", re.S)
NIVEL = re.compile(r"^RIESGO: (.+)$", re.M)

fallas = []
avisos = []


def ok(msg):
    print("  OK    %s" % msg)


def falla(msg, detalle=None):
    print("  FALLA %s" % msg)
    if detalle:
        for d in detalle[:15]:
            print("        %s" % d)
        if len(detalle) > 15:
            print("        ... y %d mas" % (len(detalle) - 15))
    fallas.append(msg)


def advertir(msg):
    print("  AVISO %s" % msg)
    avisos.append(msg)


def cargar(ruta):
    if not os.path.exists(ruta):
        print("FALTA el archivo %s. Genera los datos antes de validar." % ruta)
        sys.exit(1)
    ejemplos, malas = [], []
    for i, linea in enumerate(open(ruta, encoding="utf-8"), 1):
        linea = linea.strip()
        if not linea:
            continue
        try:
            ejemplos.append((i, json.loads(linea)))
        except json.JSONDecodeError as e:
            malas.append("linea %d: JSON invalido (%s)" % (i, e))
    return ejemplos, malas


def normaliza(t):
    return re.sub(r"\s+", " ", t.strip().lower())


# --- (a) estructura ---------------------------------------------------------
print("\n(a) Estructura de los mensajes")
datos = {}
for ruta in (CORPUS, EVAL):
    ejemplos, malas = cargar(ruta)
    datos[ruta] = ejemplos
    problemas = list(malas)
    for n, ej in ejemplos:
        msgs = ej.get("messages")
        if not isinstance(msgs, list) or len(msgs) != 2:
            problemas.append("linea %d: se esperaban 2 mensajes, hay %s" % (n, len(msgs) if isinstance(msgs, list) else "?"))
            continue
        if msgs[0].get("role") != "user" or msgs[1].get("role") != "assistant":
            problemas.append("linea %d: roles %s (se espera user, assistant)" % (n, [m.get("role") for m in msgs]))
        if not (msgs[0].get("content") or "").strip() or not (msgs[1].get("content") or "").strip():
            problemas.append("linea %d: contenido vacio" % n)
    if problemas:
        falla("%s: %d lineas con estructura invalida" % (ruta, len(problemas)), problemas)
    else:
        ok("%s: %d ejemplos con estructura valida" % (ruta, len(ejemplos)))

# --- (b) formato de salida --------------------------------------------------
print("\n(b) Formato RIESGO / BANDERAS / EXPLICACION")
for ruta, ejemplos in datos.items():
    rotas = []
    for n, ej in ejemplos:
        try:
            resp = ej["messages"][1]["content"]
        except (KeyError, IndexError, TypeError):
            continue
        if not FORMATO.match(resp + "\n"):
            rotas.append("linea %d: %s" % (n, resp[:80].replace("\n", " | ")))
    if rotas:
        falla("%s: %d/%d respuestas no cumplen el formato" % (ruta, len(rotas), len(ejemplos)), rotas)
    else:
        ok("%s: 100%% de las respuestas cumplen el formato" % ruta)

# --- (c) etiquetas validas --------------------------------------------------
print("\n(c) Valores de RIESGO")
VALIDOS = {"bajo", "medio", "alto"}
niveles = {}
for ruta, ejemplos in datos.items():
    malos, vistos = [], []
    for n, ej in ejemplos:
        try:
            m = NIVEL.search(ej["messages"][1]["content"])
        except (KeyError, IndexError, TypeError):
            continue
        valor = m.group(1) if m else "<sin RIESGO>"
        vistos.append(valor)
        if valor not in VALIDOS:
            malos.append("linea %d: RIESGO='%s'" % (n, valor))
    niveles[ruta] = vistos
    if malos:
        falla("%s: %d etiquetas invalidas" % (ruta, len(malos)), malos)
    else:
        ok("%s: todas las etiquetas son bajo/medio/alto en minusculas" % ruta)

# --- (c.1) catalogo contractual --------------------------------------------
print("\n(c.1) Banderas del catalogo contractual")
CATALOGO = {
    normalizar_bandera(bandera)
    for banderas in CATALOGO_POR_GRAVEDAD.values()
    for bandera in banderas
} | {normalizar_bandera(BANDERA_MENORES), normalizar_bandera(BANDERA_SIN_ALERTAS)}
for ruta, ejemplos in datos.items():
    fuera = []
    for n, ej in ejemplos:
        analisis = parsear_salida_modelo(ej["messages"][1]["content"])
        for bandera in analisis.get("banderas", []):
            if normalizar_bandera(bandera) not in CATALOGO:
                fuera.append("linea %d: %s" % (n, bandera))
    if fuera:
        falla(
            "%s: %d banderas fuera del catalogo; ejecuta normalizar_catalogo.py --aplicar"
            % (ruta, len(fuera)),
            fuera,
        )
    else:
        ok("%s: todas las banderas usan frases contractuales" % ruta)

# --- (d) duplicados ---------------------------------------------------------
print("\n(d) Duplicados y casi-duplicados")
for ruta, ejemplos in datos.items():
    exactos, casi = [], []
    vistos_full, vistos_100 = {}, {}
    for n, ej in ejemplos:
        try:
            u = normaliza(ej["messages"][0]["content"])
        except (KeyError, IndexError, TypeError):
            continue
        if u in vistos_full:
            exactos.append("linea %d duplica la linea %d" % (n, vistos_full[u]))
        else:
            vistos_full[u] = n
        pref = u[:100]
        if pref in vistos_100:
            casi.append("linea %d ~ linea %d: %s..." % (n, vistos_100[pref], pref[:70]))
        else:
            vistos_100[pref] = n
    if exactos or casi:
        falla("%s: %d duplicados exactos, %d casi-duplicados" % (ruta, len(exactos), len(casi)), exactos + casi)
    else:
        ok("%s: sin duplicados ni casi-duplicados" % ruta)

# --- (e) fuga de datos ------------------------------------------------------
print("\n(e) Fuga de evaluacion hacia el corpus")
users_corpus = {}
for n, ej in datos[CORPUS]:
    try:
        users_corpus[normaliza(ej["messages"][0]["content"])] = n
    except (KeyError, IndexError, TypeError):
        pass
fugas = []
for n, ej in datos[EVAL]:
    try:
        u = normaliza(ej["messages"][0]["content"])
    except (KeyError, IndexError, TypeError):
        continue
    if u in users_corpus:
        fugas.append("evaluacion linea %d == corpus linea %d" % (n, users_corpus[u]))
        continue
    # coincidencia parcial: el aviso de evaluacion contenido en alguno del corpus
    cuerpo = u.split("\n")[-1] if "\n" in u else u
    for uc, nc in users_corpus.items():
        if len(cuerpo) > 60 and cuerpo in uc:
            fugas.append("evaluacion linea %d contenida en corpus linea %d" % (n, nc))
            break
if fugas:
    falla("%d ejemplos de evaluacion aparecen en el corpus" % len(fugas), fugas)
else:
    ok("ningun aviso de evaluacion aparece en el corpus")

# --- (f) distribucion (solo advierte) ---------------------------------------
print("\n(f) Distribucion por clase de riesgo")
for ruta in (CORPUS, EVAL):
    c = Counter(niveles.get(ruta, []))
    total = sum(c.values()) or 1
    print("  %s (n=%d)" % (ruta, total))
    for k in ("alto", "medio", "bajo"):
        pct = 100.0 * c.get(k, 0) / total
        print("    %-6s %4d  %5.1f%%" % (k, c.get(k, 0), pct))
    for k in ("alto", "medio", "bajo"):
        if 100.0 * c.get(k, 0) / total < 15:
            advertir("%s: la clase '%s' tiene menos del 15%% del total" % (ruta, k))
    if c.get("medio", 0) == 0:
        advertir("%s: no hay casos de riesgo medio; sin ambiguos el modelo sale paranoico" % ruta)

# --- (g) longitud (solo advierte) -------------------------------------------
print("\n(g) Longitud en tokens")
try:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODELO)
    for ruta, ejemplos in datos.items():
        largos = []
        for _, ej in ejemplos:
            try:
                texto = tok.apply_chat_template(ej["messages"], tokenize=False)
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            largos.append(len(tok(texto, add_special_tokens=False)["input_ids"]))
        if not largos:
            continue
        largos.sort()
        p95 = largos[int(len(largos) * 0.95) - 1]
        print("  %s: mediana %d, p95 %d, maximo %d tokens" % (ruta, largos[len(largos) // 2], p95, largos[-1]))
        if p95 > 900:
            advertir("%s: p95 = %d tokens (> 900); considera max_length mayor o recortar" % (ruta, p95))
except (OSError, ImportError) as e:
    advertir("no se pudo cargar el tokenizer para medir longitudes (%s)" % e)

# --- veredicto --------------------------------------------------------------
print("\n" + "=" * 60)
if fallas:
    print("COMPUERTA 1: NO PASA (%d verificaciones bloqueantes fallaron)" % len(fallas))
    for f in fallas:
        print("  - %s" % f)
    sys.exit(1)
print("COMPUERTA 1: PASA")
if avisos:
    print("(%d advertencias no bloqueantes)" % len(avisos))
sys.exit(0)
