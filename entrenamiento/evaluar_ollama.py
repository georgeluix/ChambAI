# -*- coding: utf-8 -*-
"""Evaluacion del stack REAL de la demo: Gemma 4 E2B + few-shot via Ollama.

Corre los 20 casos de evaluacion.jsonl (escritos a mano, nunca vistos por
ningun entrenamiento) contra el mismo camino que usara el backend. Mide lo que
el modelo hace solo, SIN las reglas deterministas del backend: el numero real
de la demo sera igual o mejor, porque las reglas fuerzan "alto" en menores y
cobros aunque el modelo se equivoque.

Solo usa la libreria estandar: se ejecuta con el Python de Windows, donde vive
Ollama.

Uso (PowerShell):  python evaluar_ollama.py
"""
import json
import os
import re
import sys
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(AQUI, "evaluacion.jsonl")
SALIDA = os.path.join(AQUI, "resultados-evaluacion-ollama.json")
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODELO = os.environ.get("MODELO_OLLAMA", "gemma4:e2b")

FORMATO = re.compile(r"^RIESGO: (bajo|medio|alto)\nBANDERAS:\n(?:- .+\n)+EXPLICACION: .+", re.S)
NIVELES = ("alto", "medio", "bajo")

# El mismo few-shot del backend: un ejemplo por nivel, con el catalogo de frases
FEWSHOT = [
    ("Analiza este aviso de empleo:\n\nSe necesita señoritas para night club en Iquitos. "
     "Ganas 400 soles diarios. Pagamos tu pasaje y te quedas en el local. Escribir al WhatsApp.",
     "RIESGO: alto\nBANDERAS:\n"
     "- Filtro por sexo, edad y apariencia fisica sin relacion con la funcion\n"
     "- Remuneracion desproporcionada para el puesto y sin sustento\n"
     "- Traslado fuera de la ciudad con pasaje cubierto por el empleador\n"
     "- Alojamiento dentro del centro de trabajo\n"
     "EXPLICACION: El aviso concentra señales de captacion: filtro por apariencia, pago "
     "irreal y alojamiento en el propio local, que es el mecanismo para aislar a la victima. "
     "No respondas y reporta a la Linea 1818."),
    ("Analiza este aviso de empleo:\n\nContact Center Lima Norte busca teleoperadores turno "
     "noche. Bono nocturno de ley y movilidad de retorno. Sueldo a conversar en la entrevista. "
     "Coordinar por WhatsApp con reclutamiento.",
     "RIESGO: medio\nBANDERAS:\n- Trabajo en horario nocturno\n"
     "- Remuneracion no especificada en el aviso\n- Postulacion por mensajeria personal\n"
     "EXPLICACION: La empresa esta identificada y menciona beneficios de ley, pero omitir el "
     "sueldo y postular solo por mensajeria impide verificar la oferta. Confirma el RUC en "
     "SUNAT antes de asistir."),
    ("Analiza este aviso de empleo:\n\nSupermercados Mi Barrio S.A.C. (RUC 20512447890) "
     "convoca cajeros en Los Olivos. Requisitos: secundaria completa, 6 meses de experiencia. "
     "S/ 1350 en planilla con EsSalud y CTS. Postular en nuestra bolsa de trabajo.",
     "RIESGO: bajo\nBANDERAS:\n- Ninguna señal de alerta detectada\n"
     "EXPLICACION: El aviso identifica a la empresa con RUC, detalla requisitos proporcionales "
     "y ofrece los beneficios de ley por un canal institucional. No se observan señales de "
     "captacion."),
]

SISTEMA = (
    "Eres el analizador de Chamba Segura. Evaluas avisos de trabajo peruanos para detectar "
    "señales de captacion vinculada a trata de personas. Respondes SIEMPRE y UNICAMENTE con "
    "este formato exacto, sin markdown ni texto adicional:\n"
    "RIESGO: <bajo|medio|alto>\nBANDERAS:\n- <una por linea>\nEXPLICACION: <2 o 3 oraciones>\n"
    "Si el riesgo es bajo, la unica bandera es '- Ninguna señal de alerta detectada'. "
    "En riesgo alto recomienda reportar a la Linea 1818."
)


def llamar(mensajes):
    cuerpo = json.dumps({
        "model": MODELO,
        "messages": mensajes,
        "stream": False,
        "options": {"num_ctx": 16384, "temperature": 0},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/chat", data=cuerpo,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    texto = resp.get("message", {}).get("content", "").strip()
    n_tok = resp.get("eval_count", 0)
    dur = resp.get("eval_duration", 0) / 1e9  # generacion pura, sin prompt
    return texto, (n_tok / dur if dur else n_tok / dt), dt


def main():
    casos = []
    for linea in open(EVAL, encoding="utf-8"):
        if not linea.strip():
            continue
        ej = json.loads(linea)
        esperado = re.match(r"RIESGO: (\w+)", ej["messages"][1]["content"]).group(1)
        casos.append((ej["messages"][0]["content"], esperado))

    print("Evaluando %d casos contra %s (%s)\n" % (len(casos), MODELO, OLLAMA))

    base = [{"role": "system", "content": SISTEMA}]
    for pregunta, respuesta in FEWSHOT:
        base.append({"role": "user", "content": pregunta})
        base.append({"role": "assistant", "content": respuesta})

    aciertos = formato_ok = graves = omisiones_alto = 0
    velocidades, matriz, fallos, detalles = [], {}, [], []

    for i, (aviso, esperado) in enumerate(casos, 1):
        try:
            texto, tok_s, dt = llamar(base + [{"role": "user", "content": aviso}])
        except Exception as e:  # noqa: BLE001 - reportar y seguir
            print("  ERROR caso %2d: %s" % (i, e))
            continue
        velocidades.append(tok_s)

        ok_formato = bool(FORMATO.match(texto + "\n"))
        formato_ok += ok_formato
        m = re.match(r"^RIESGO: (\w+)", texto)
        obtenido = m.group(1) if m else "?"
        matriz[(esperado, obtenido)] = matriz.get((esperado, obtenido), 0) + 1

        marca = "OK  "
        if obtenido == esperado:
            aciertos += 1
        else:
            marca = "MAL "
            fallos.append((i, esperado, obtenido, aviso[:70]))
            if {esperado, obtenido} == {"alto", "bajo"}:
                graves += 1
                marca = "GRAVE"
            if esperado == "alto" and obtenido != "alto":
                omisiones_alto += 1
                marca = "GRAVE"
        print("  %-5s caso %2d  esperado %-5s  obtenido %-5s  formato %s  (%.0f tok/s, %.1f s)"
              % (marca, i, esperado, obtenido, "si" if ok_formato else "NO", tok_s, dt))
        detalles.append({"caso": i, "esperado": esperado, "obtenido": obtenido,
                         "formato_valido": ok_formato, "tok_s": round(tok_s, 1),
                         "respuesta": texto})

    n = len(velocidades) or 1
    print("\n" + "=" * 66)
    print("RESULTADO: Gemma 4 E2B + few-shot via Ollama (stack de la demo)")
    print("=" * 66)
    print("  exactitud de RIESGO   : %d/%d  (%.0f%%)" % (aciertos, n, 100.0 * aciertos / n))
    print("  omisiones de alto     : %d  (avisos peligrosos subestimados)" % omisiones_alto)
    print("  confusiones alto<->bajo: %d" % graves)
    print("  formato parseable     : %d/%d  (%.0f%%)" % (formato_ok, n, 100.0 * formato_ok / n))
    print("  velocidad media       : %.0f tok/s" % (sum(velocidades) / n))
    print("\n  esperado \\ obtenido    " + "".join("%-8s" % x for x in NIVELES + ("?",)))
    for esperado in NIVELES:
        fila = "".join("%-8d" % matriz.get((esperado, o), 0) for o in NIVELES + ("?",))
        print("  %-22s %s" % (esperado, fila))
    if fallos:
        print("\n  fallos:")
        for i, esp, obt, txt in fallos:
            print("    caso %2d  %s -> %s  | %s..." % (i, esp, obt, txt.replace("\n", " ")))
    print("\n  Nota: medido SIN las reglas deterministas del backend (menores de")
    print("  edad y cobros fuerzan 'alto' por codigo); la demo real solo mejora.")

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump({"modelo": MODELO, "exactitud_pct": round(100.0 * aciertos / n, 1),
                   "omisiones_alto": omisiones_alto, "graves": graves,
                   "formato_pct": round(100.0 * formato_ok / n, 1),
                   "tok_s_media": round(sum(velocidades) / n, 1),
                   "casos": detalles}, f, ensure_ascii=False, indent=1)
    print("\nGuardado en %s" % os.path.basename(SALIDA))
    return 0


if __name__ == "__main__":
    sys.exit(main())
