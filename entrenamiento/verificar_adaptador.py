# -*- coding: utf-8 -*-
"""COMPUERTA 4: separa "el entrenamiento termino" de "el adaptador sirve".

Carga el modelo base + el adaptador LoRA y verifica sobre 3 casos fijos que:
  - las 3 salidas cumplen el formato RIESGO/BANDERAS/EXPLICACION
  - el fraudulento obvio no salga "bajo" y el legitimo obvio no salga "alto"
    (esto detecta el colapso a una sola clase, que es el fallo mas comun)
  - mide tokens/segundo, dato que decide si sirve para la demo en vivo

Uso: python verificar_adaptador.py [ruta_adaptador]
"""
import os
import re
import sys
import time

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch  # noqa: E402
from peft import PeftModel  # noqa: E402

from receta import cargar_base  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
ADAPTADOR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "adaptador-lora")

FORMATO = re.compile(r"^RIESGO: (bajo|medio|alto)\nBANDERAS:\n(?:- .+\n)+EXPLICACION: .+", re.S)
PREFIJO = "Analiza este aviso de empleo:\n\n"

CASOS = [
    ("fraudulento obvio",
     "URGENTE!! Se necesitan señoritas de 18 a 24 años para trabajar en night club en Iquitos. "
     "Ganas 500 soles diarios. Nosotros pagamos tu pasaje y te quedas en el mismo local. "
     "No necesitas experiencia ni CV. Manda tu foto de cuerpo entero al WhatsApp 987 111 222.",
     {"prohibido": "bajo"}),
    ("legitimo obvio",
     "Supermercados Mi Barrio S.A.C. (RUC 20512447890) convoca a cajeros para su tienda de Los Olivos. "
     "Requisitos: secundaria completa, 6 meses de experiencia en manejo de efectivo. "
     "S/ 1350 mensuales en planilla, EsSalud, gratificaciones y CTS. "
     "Postular en nuestra bolsa de trabajo: empleos.mibarrio.com.pe",
     {"prohibido": "alto"}),
    ("ambiguo",
     "Contact Center Lima Norte necesita teleoperadores para turno noche de 10pm a 6am. "
     "Se paga bono nocturno de ley y hay movilidad de retorno. El sueldo lo conversamos en la entrevista. "
     "Coordinar por WhatsApp 991 447 203 con el area de reclutamiento.",
     {}),
]


def cargar():
    if not os.path.isdir(ADAPTADOR):
        print("FALTA el adaptador en %s" % ADAPTADOR)
        print("Corre primero: python entrenar.py --completo")
        sys.exit(1)
    tok, base = cargar_base()
    model = PeftModel.from_pretrained(base, ADAPTADOR)
    model.eval()
    print("Modelo + adaptador cargados. VRAM: %.1f GB\n" % (torch.cuda.memory_allocated() / 1e9))
    return tok, model


def generar(tok, model, aviso):
    msgs = [{"role": "user", "content": PREFIJO + aviso}]
    entrada = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    ids = tok(entrada, return_tensors="pt", add_special_tokens=False).to(model.device)
    t0 = time.time()
    with torch.no_grad():
        salida = model.generate(**ids, max_new_tokens=256, do_sample=False,
                                pad_token_id=tok.eos_token_id)
    dt = time.time() - t0
    nuevos = salida[0][ids["input_ids"].shape[1]:]
    texto = tok.decode(nuevos, skip_special_tokens=True).strip()
    return texto, len(nuevos), dt


def main():
    tok, model = cargar()
    fallas = []
    niveles, velocidades = [], []

    for etiqueta, aviso, regla in CASOS:
        print("=" * 72)
        print("CASO: %s" % etiqueta)
        print("-" * 72)
        texto, n_tok, dt = generar(tok, model, aviso)
        print(texto)
        print("-" * 72)
        velocidades.append(n_tok / dt if dt else 0)
        print("  %d tokens en %.1f s  (%.1f tok/s)" % (n_tok, dt, n_tok / dt if dt else 0))

        # (c) formato
        if FORMATO.match(texto + "\n"):
            print("  OK    formato RIESGO/BANDERAS/EXPLICACION correcto")
        else:
            print("  FALLA la salida no cumple el formato")
            fallas.append("%s: formato roto" % etiqueta)

        # (d) colapso a una clase
        m = re.match(r"^RIESGO: (\w+)", texto)
        nivel = m.group(1) if m else "?"
        niveles.append(nivel)
        if regla.get("prohibido"):
            if nivel == regla["prohibido"]:
                print("  FALLA el caso '%s' salio '%s'" % (etiqueta, nivel))
                fallas.append("%s clasificado como '%s'" % (etiqueta, nivel))
            else:
                print("  OK    clasificado '%s' (no '%s')" % (nivel, regla["prohibido"]))
        else:
            print("  info  clasificado '%s'" % nivel)
        print()

    if len(set(niveles)) == 1:
        print("  FALLA los 3 casos salieron '%s': el modelo colapso a una sola clase" % niveles[0])
        fallas.append("colapso a una sola clase")

    print("=" * 60)
    print("Velocidad media: %.1f tok/s" % (sum(velocidades) / len(velocidades)))
    print("Etiquetas: %s" % ", ".join("%s=%s" % (c[0], n) for c, n in zip(CASOS, niveles)))
    print("=" * 60)
    if fallas:
        print("COMPUERTA 4: NO PASA")
        for f in fallas:
            print("  - %s" % f)
        print("\nAccion: probar un checkpoint anterior de ~/entrenamiento-out/checkpoints/")
        print("  python verificar_adaptador.py ~/entrenamiento-out/checkpoints/checkpoint-100")
        print("Si ninguno pasa: few-shot con el modelo base y seguir con la demo.")
        return 1
    print("COMPUERTA 4: PASA - integrar al pipeline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
