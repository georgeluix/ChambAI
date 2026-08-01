# -*- coding: utf-8 -*-
"""Evaluacion comparativa: Gemma 4 base (few-shot) vs Gemma 4 + LoRA.

Los 20 casos de evaluacion.jsonl estan escritos a mano, con redaccion de
Facebook/WhatsApp real, y nunca entraron al corpus (la Compuerta 1 verifica que
no haya fuga). Miden generalizacion, no memorizacion.

Responde la pregunta que la Compuerta 4 no responde: no si el modelo esta roto,
sino si el fine-tune sirvio para algo. Si el base con few-shot rinde igual, la
decision correcta es servir con Ollama y ahorrarse el despliegue con
transformers; eso es informacion util, no un fracaso.

Metricas:
  - exactitud de RIESGO (la que decide si la herramienta acierta)
  - omisiones de alto riesgo: cualquier aviso alto clasificado como medio o bajo
  - formato valido (si el frontend puede parsear la respuesta)
  - precision/recall de banderas tras canonicalizarlas como lo hace el backend
  - porcentaje de banderas que ya salen con la frase exacta del catalogo
  - tokens/segundo

Uso:
  python evaluar.py                 # compara base vs adaptador
  python evaluar.py --solo-base     # solo el modelo base con few-shot
"""
import json
import os
import re
import sys
import time

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch  # noqa: E402

from receta import cargar_base  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(AQUI, "..", "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from extractor import (  # noqa: E402
    BANDERA_SIN_ALERTAS,
    CATALOGO_POR_GRAVEDAD,
    canonizar_bandera,
    normalizar,
    parsear_salida_modelo,
)

EVAL = os.path.join(AQUI, "evaluacion.jsonl")
ADAPTADOR = os.path.join(AQUI, "adaptador-lora")
FORMATO = re.compile(r"^RIESGO: (bajo|medio|alto)\nBANDERAS:\n(?:- .+\n)+EXPLICACION: .+", re.S)
NIVELES = ("alto", "medio", "bajo")
CATALOGO = {
    normalizar(bandera)
    for banderas in CATALOGO_POR_GRAVEDAD.values()
    for bandera in banderas
} | {normalizar(BANDERA_SIN_ALERTAS)}

# Few-shot para el modelo base: sin esto no conoce el formato de salida y la
# comparacion seria injusta (estariamos midiendo si adivina un formato que
# nadie le enseño, no si sabe evaluar el riesgo).
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


def construir_mensajes(aviso, con_fewshot):
    msgs = []
    if con_fewshot:
        for pregunta, respuesta in FEWSHOT:
            msgs.append({"role": "user", "content": pregunta})
            msgs.append({"role": "assistant", "content": respuesta})
    msgs.append({"role": "user", "content": aviso})
    return msgs


def generar(tok, model, aviso, con_fewshot):
    entrada = tok.apply_chat_template(construir_mensajes(aviso, con_fewshot),
                                      tokenize=False, add_generation_prompt=True)
    ids = tok(entrada, return_tensors="pt", add_special_tokens=False).to(model.device)
    t0 = time.time()
    with torch.no_grad():
        salida = model.generate(**ids, max_new_tokens=256, do_sample=False,
                                pad_token_id=tok.eos_token_id)
    dt = time.time() - t0
    nuevos = salida[0][ids["input_ids"].shape[1]:]
    return tok.decode(nuevos, skip_special_tokens=True).strip(), len(nuevos), dt


def banderas_de(texto):
    analisis = parsear_salida_modelo(texto)
    if not analisis["formato_valido"]:
        return set(), False
    exactas = all(normalizar(b) in CATALOGO for b in analisis["banderas"])
    canonicas = {
        normalizar(canonica)
        for bandera in analisis["banderas"]
        for canonica in canonizar_bandera(bandera)
        if normalizar(canonica) != normalizar(BANDERA_SIN_ALERTAS)
    }
    return canonicas, exactas


def evaluar(tok, model, casos, etiqueta, con_fewshot):
    aciertos = formato_ok = graves = omisiones_altas = catalogo_ok = 0
    verdaderas_positivas = falsas_positivas = falsas_negativas = 0
    velocidades, matriz, fallos = [], {}, []

    print("\n" + "=" * 72)
    print("EVALUANDO: %s" % etiqueta)
    print("=" * 72)

    for i, (aviso, esperado, banderas_esperadas) in enumerate(casos, 1):
        texto, n_tok, dt = generar(tok, model, aviso, con_fewshot)
        velocidades.append(n_tok / dt if dt else 0)

        if FORMATO.match(texto + "\n"):
            formato_ok += 1
        banderas_obtenidas, exactas = banderas_de(texto)
        catalogo_ok += int(exactas)
        verdaderas_positivas += len(banderas_obtenidas & banderas_esperadas)
        falsas_positivas += len(banderas_obtenidas - banderas_esperadas)
        falsas_negativas += len(banderas_esperadas - banderas_obtenidas)
        m = re.match(r"^RIESGO: (\w+)", texto)
        obtenido = m.group(1) if m else "?"
        matriz[(esperado, obtenido)] = matriz.get((esperado, obtenido), 0) + 1

        if obtenido == esperado:
            aciertos += 1
            marca = "OK  "
        else:
            marca = "MAL "
            fallos.append((i, esperado, obtenido, aviso[:70]))
            if {esperado, obtenido} == {"alto", "bajo"}:
                graves += 1
                marca = "GRAVE"
            if esperado == "alto" and obtenido != "alto":
                omisiones_altas += 1
                marca = "GRAVE"
        print("  %-5s caso %2d  esperado %-5s  obtenido %-5s  (%.0f tok/s)"
              % (marca, i, esperado, obtenido, n_tok / dt if dt else 0))

    n = len(casos)
    precision = verdaderas_positivas / max(1, verdaderas_positivas + falsas_positivas)
    recall = verdaderas_positivas / max(1, verdaderas_positivas + falsas_negativas)
    resultado = {
        "etiqueta": etiqueta,
        "exactitud": 100.0 * aciertos / n,
        "formato": 100.0 * formato_ok / n,
        "graves": graves,
        "omisiones_altas": omisiones_altas,
        "catalogo": 100.0 * catalogo_ok / n,
        "precision_banderas": 100.0 * precision,
        "recall_banderas": 100.0 * recall,
        "tok_s": sum(velocidades) / len(velocidades),
        "matriz": matriz,
        "fallos": fallos,
    }
    print("\n  exactitud %.0f%% (%d/%d) | formato %.0f%% | omisiones alto %d | %.1f tok/s"
          % (resultado["exactitud"], aciertos, n, resultado["formato"],
             omisiones_altas, resultado["tok_s"]))
    print("  catalogo exacto %.0f%% | banderas precision %.0f%% | recall %.0f%%"
          % (resultado["catalogo"], resultado["precision_banderas"],
             resultado["recall_banderas"]))
    return resultado


def matriz_confusion(matriz):
    print("\n  esperado \\ obtenido    " + "".join("%-8s" % n for n in NIVELES))
    for esperado in NIVELES:
        fila = "".join("%-8d" % matriz.get((esperado, obt), 0) for obt in NIVELES)
        print("  %-22s %s" % (esperado, fila))


def main():
    casos = []
    for linea in open(EVAL, encoding="utf-8"):
        if not linea.strip():
            continue
        ej = json.loads(linea)
        respuesta = ej["messages"][1]["content"]
        esperado = re.match(r"RIESGO: (\w+)", respuesta).group(1)
        banderas, _ = banderas_de(respuesta)
        casos.append((ej["messages"][0]["content"], esperado, banderas))
    print("Casos de evaluacion: %d (nunca vistos en el entrenamiento)" % len(casos))

    tok, base = cargar_base()
    base.eval()
    resultados = [evaluar(tok, base, casos, "Gemma 4 E2B base + few-shot", con_fewshot=True)]

    if "--solo-base" not in sys.argv:
        if not os.path.isdir(ADAPTADOR):
            print("\nNo hay adaptador en %s todavia; solo se evaluo el base." % ADAPTADOR)
        else:
            from peft import PeftModel
            model = PeftModel.from_pretrained(base, ADAPTADOR)
            model.eval()
            # el fine-tune aprendio el formato: no necesita los ejemplos en el prompt
            resultados.append(evaluar(tok, model, casos, "Gemma 4 E2B + LoRA", con_fewshot=False))

    print("\n" + "=" * 72)
    print("COMPARATIVA")
    print("=" * 72)
    print("  %-32s %10s %10s %10s %9s" %
          ("configuracion", "exactitud", "formato", "omite alto", "tok/s"))
    for r in resultados:
        print("  %-32s %9.0f%% %9.0f%% %10d %9.1f"
              % (r["etiqueta"], r["exactitud"], r["formato"],
                 r["omisiones_altas"], r["tok_s"]))

    for r in resultados:
        print("\n--- %s ---" % r["etiqueta"])
        matriz_confusion(r["matriz"])
        if r["fallos"]:
            print("  fallos:")
            for i, esp, obt, txt in r["fallos"]:
                print("    caso %2d  %s -> %s  | %s..." % (i, esp, obt, txt.replace("\n", " ")))

    if len(resultados) == 2:
        base_r, lora_r = resultados
        delta = lora_r["exactitud"] - base_r["exactitud"]
        print("\n" + "=" * 72)
        print("  El fine-tune %s la exactitud en %+.0f puntos (%.0f%% -> %.0f%%)"
              % ("mejoro" if delta > 0 else "empeoro", delta,
                 base_r["exactitud"], lora_r["exactitud"]))
        print("  Errores graves (alto<->bajo): %d -> %d" % (base_r["graves"], lora_r["graves"]))
        print("  Omisiones de avisos altos: %d -> %d" %
              (base_r["omisiones_altas"], lora_r["omisiones_altas"]))
        if (delta <= 0 and lora_r["omisiones_altas"] >= base_r["omisiones_altas"]):
            print("\n  RECOMENDACION: el fine-tune no aporta. Sirve el modelo base con few-shot")
            print("  desde Ollama y evita el despliegue con transformers.")
        else:
            print("\n  RECOMENDACION: usar el adaptador. Ganancia real sobre casos no vistos.")

    with open(os.path.join(AQUI, "resultados-evaluacion.json"), "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in r.items() if k != "matriz"} for r in resultados],
                  f, ensure_ascii=False, indent=1)
    print("\nResultados guardados en resultados-evaluacion.json")


if __name__ == "__main__":
    sys.exit(main())
