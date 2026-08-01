# -*- coding: utf-8 -*-
"""COMPUERTA 2: verifica que el chat template se aplique bien.

Es el unico fallo que no da error: la perdida baja igual y el modelo aprende
basura. Solo se ve mirando el texto renderizado.

Gemma 4 usa <|turn>rol ... <turn|>, NO <start_of_turn> (eso era Gemma 2/3).
Verificado en chat_template.jinja lineas 234 y 382.

Uso: python inspeccionar_template.py
"""
import json
import os
import sys

from transformers import AutoTokenizer

MODELO = os.environ.get("MODELO_BASE", "/home/abel_brayan/gemma-4-e2b")
CORPUS = "corpus.jsonl"
MAX_LEN = int(os.environ.get("MAX_LEN", "1024"))

APERTURA_USER = "<|turn>user"
APERTURA_MODEL = "<|turn>model"
CIERRE = "<turn|>"

fallas = []

if not os.path.exists(CORPUS):
    print("FALTA %s. Genera el corpus antes de inspeccionar el template." % CORPUS)
    sys.exit(1)

ejemplos = [json.loads(l) for l in open(CORPUS, encoding="utf-8") if l.strip()]
tok = AutoTokenizer.from_pretrained(MODELO)

# --- (a) render del primer y ultimo ejemplo ---------------------------------
for etiqueta, ej in (("PRIMER", ejemplos[0]), ("ULTIMO", ejemplos[-1])):
    print("=" * 72)
    print("%s EJEMPLO RENDERIZADO" % etiqueta)
    print("=" * 72)
    print(tok.apply_chat_template(ej["messages"], tokenize=False))
    print()

render = tok.apply_chat_template(ejemplos[0]["messages"], tokenize=False)

# --- (b) marcadores de turno ------------------------------------------------
print("(b) Marcadores de turno de Gemma 4")
for marcador in (APERTURA_USER, APERTURA_MODEL, CIERRE):
    if marcador in render:
        print("  OK    '%s' presente" % marcador)
    else:
        print("  FALLA '%s' AUSENTE" % marcador)
        fallas.append("falta el marcador %s" % marcador)

if fallas and "<start_of_turn>" in render:
    print("\n  DIAGNOSTICO: el template renderiza <start_of_turn> (Gemma 2/3).")
    print("  El tokenizer no corresponde a Gemma 4 o chat_template.jinja fue reemplazado.")
    print("  Revisa %s/chat_template.jinja" % MODELO)
elif fallas:
    print("\n  DIAGNOSTICO: el template no aplico los marcadores esperados.")
    print("  Revisa que tokenizer_config.json apunte a chat_template.jinja y que")
    print("  los mensajes usen los roles 'user' y 'assistant'.")

# --- (c) orden de los roles -------------------------------------------------
print("\n(c) Orden de los roles")
contenido_assistant = ejemplos[0]["messages"][1]["content"][:40]
pos_model = render.find(APERTURA_MODEL)
pos_resp = render.find(contenido_assistant)
if pos_model == -1 or pos_resp == -1:
    print("  FALLA no se pudo ubicar el turno del modelo o su contenido")
    fallas.append("no se ubico el contenido del assistant en el render")
elif pos_resp > pos_model:
    print("  OK    la respuesta del assistant aparece despues de '%s'" % APERTURA_MODEL)
else:
    print("  FALLA la respuesta del assistant aparece ANTES de '%s': roles invertidos" % APERTURA_MODEL)
    fallas.append("roles invertidos en el render")

pos_user = render.find(APERTURA_USER)
if pos_user != -1 and pos_model != -1 and pos_user > pos_model:
    print("  FALLA el turno 'user' aparece despues del turno 'model'")
    fallas.append("orden de turnos invertido")

# --- (d) longitud del ejemplo mas largo -------------------------------------
print("\n(d) Longitud del ejemplo mas largo")
largos = [(len(tok(tok.apply_chat_template(e["messages"], tokenize=False),
                   add_special_tokens=False)["input_ids"]), i)
          for i, e in enumerate(ejemplos)]
n_tokens, idx = max(largos)
print("  ejemplo %d: %d tokens (max_length configurado: %d)" % (idx, n_tokens, MAX_LEN))
if n_tokens > MAX_LEN:
    truncados = sum(1 for n, _ in largos if n > MAX_LEN)
    print("  AVISO se truncan %d tokens del ejemplo mas largo; %d/%d ejemplos superan max_length"
          % (n_tokens - MAX_LEN, truncados, len(ejemplos)))
    print("  Si los truncados cortan la EXPLICACION, el modelo aprende respuestas incompletas.")
else:
    print("  OK    ningun ejemplo se trunca con max_length=%d" % MAX_LEN)

# --- veredicto --------------------------------------------------------------
print("\n" + "=" * 60)
if fallas:
    print("COMPUERTA 2: NO PASA")
    for f in fallas:
        print("  - %s" % f)
    sys.exit(1)
print("COMPUERTA 2: PASA")
sys.exit(0)
