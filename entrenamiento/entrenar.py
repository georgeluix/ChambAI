# -*- coding: utf-8 -*-
"""Entrenamiento LoRA de Chamba Segura sobre Gemma 4 E2B en 8 GB de VRAM.

La receta de carga vive en receta.py, compartida con verificar_adaptador.py
para que el adaptador no se entrene sobre una configuracion y se sirva sobre
otra. Los cuatro fixes y su porque estan documentados alli.

Uso:
  python entrenar.py --canario     # COMPUERTA 3: 20 steps, ~2 min
  nohup python entrenar.py --completo > train.log 2>&1 &
"""
import argparse
import os
import shutil
import sys
import time

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch  # noqa: E402
from datasets import load_dataset  # noqa: E402
from transformers import Trainer, TrainingArguments, DataCollatorForSeq2Seq  # noqa: E402

from receta import cargar_base, preparar, envolver_lora, MAX_LEN  # noqa: E402

CORPUS = "corpus.jsonl"
# Los checkpoints van a disco nativo de WSL: escribirlos en /mnt/c via 9p es lento.
SALIDA_BASE = os.environ.get("SALIDA_BASE", os.path.expanduser("~/entrenamiento-out"))
AQUI = os.path.dirname(os.path.abspath(__file__))
VRAM_LIMITE = 7.6


def cargar_modelo():
    tok, model = cargar_base()
    model = preparar(model)
    model = envolver_lora(model)
    return tok, model


def cargar_datos(tok):
    """Tokeniza a mano y enmascara el prompt con -100. NO delegar esto a TRL.

    Historial de dos entrenamientos fallidos por confiar en la libreria:

    1. Formato 'messages': SFTTrainer calcula la perdida sobre TODO el texto.
       Con avisos de ~200 tokens y respuestas de ~100, dos tercios de la señal
       se gastaban enseñando al modelo a reproducir avisos en vez de a
       responder. Perdida 1.22 y mean_token_accuracy 0.91, pero el modelo
       seguia contestando en markdown generico.

    2. Formato prompt/completion con completion_only_loss=True: TRL tokeniza el
       prompt y el prompt+completion por separado y busca el prefijo comun. Con
       el chat template de Gemma 4 los dos no coinciden, TRL avisa
       "Mismatch between tokenized prompt and the start of tokenized
       prompt+completion" y termina marcando el 99% de los tokens como
       respuesta. Es decir: exactamente lo mismo que el caso 1, en silencio.

    Aqui el prompt se construye con add_generation_prompt=True, o sea el string
    EXACTO que recibira en inferencia. Asi no puede haber discrepancia entre lo
    que el modelo ve al entrenar y lo que ve al generar.
    """
    data = load_dataset("json", data_files=CORPUS, split="train")

    def preparar(ej):
        usuario, asistente = ej["messages"][0], ej["messages"][1]
        prompt = tok.apply_chat_template([usuario], tokenize=False,
                                         add_generation_prompt=True)
        completo = prompt + asistente["content"] + "<turn|>\n"
        ids_prompt = tok(prompt, add_special_tokens=False)["input_ids"]
        ids = tok(completo, add_special_tokens=False)["input_ids"][:MAX_LEN]
        # -100 en el prompt: la perdida solo mira la respuesta
        labels = [-100] * min(len(ids_prompt), len(ids)) + ids[len(ids_prompt):]
        return {"input_ids": ids, "labels": labels,
                "attention_mask": [1] * len(ids)}

    data = data.map(preparar, remove_columns=data.column_names)

    n = len(data[0]["labels"])
    con_perdida = sum(1 for x in data[0]["labels"] if x != -100)
    print("Mascara verificada: %d de %d tokens con perdida (%.0f%%) -- el resto es el prompt"
          % (con_perdida, n, 100.0 * con_perdida / n))
    if con_perdida > 0.75 * n:
        raise SystemExit("La mascara no esta funcionando: cubre casi todo el texto.")
    return data


def config_comun(output_dir, **extra):
    # Trainer estandar de transformers, no SFTTrainer: el dataset ya viene
    # tokenizado y enmascarado a mano (ver cargar_datos).
    return TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=float(os.environ.get("LR", "2e-4")),
        logging_steps=1,
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        remove_unused_columns=False,
        **extra,
    )


def crear_trainer(model, tok, data, cfg):
    # DataCollatorForSeq2Seq padea labels con -100, que es lo que necesitamos
    collator = DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100,
                                      return_tensors="pt")
    return Trainer(model=model, args=cfg, train_dataset=data, data_collator=collator)


def historial(trainer):
    logs = [l for l in trainer.state.log_history if "loss" in l]
    perdidas = [float(l["loss"]) for l in logs]
    grads = [float(l.get("grad_norm", 0) or 0) for l in logs]
    return perdidas, grads


def probar_formato(tok, model):
    """Genera sobre un aviso y verifica que salga RIESGO/BANDERAS/EXPLICACION.

    Los dos entrenamientos anteriores dieron metricas verdes (perdida 1.22 y
    0.85, precision 0.91 y 0.97) y aun asi el modelo respondia en markdown
    generico. Ninguna compuerta lo detectaba porque todas miraban numeros del
    log. Esta prueba mira lo unico que importa: lo que el modelo escribe.
    """
    import re
    formato = re.compile(r"^RIESGO: (bajo|medio|alto)\nBANDERAS:\n(?:- .+\n)+EXPLICACION: .+", re.S)
    aviso = ("Analiza este aviso de empleo:\n\nSe busca señoritas para night club en "
             "Iquitos. Pagamos tu pasaje y te quedas en el local. 400 soles diarios. "
             "Escribir al WhatsApp.")
    entrada = tok.apply_chat_template([{"role": "user", "content": aviso}],
                                      tokenize=False, add_generation_prompt=True)
    ids = tok(entrada, return_tensors="pt", add_special_tokens=False).to(model.device)
    model.eval()
    with torch.no_grad():
        salida = model.generate(**ids, max_new_tokens=160, do_sample=False,
                                pad_token_id=tok.eos_token_id)
    model.train()
    texto = tok.decode(salida[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    print("\n--- generacion de prueba ---")
    print(texto[:400])
    print("---")
    return bool(formato.match(texto + "\n")), texto


def canario():
    pasos = int(os.environ.get("PASOS_CANARIO", "60"))
    print(">>> MODO CANARIO (COMPUERTA 3): %d steps de diagnostico\n" % pasos)
    tok, model = cargar_modelo()
    data = cargar_datos(tok)
    cfg = config_comun(os.path.join(SALIDA_BASE, "canario-out"), max_steps=pasos,
                       save_strategy="no")
    trainer = crear_trainer(model, tok, data, cfg)
    t0 = time.time()
    trainer.train()
    seg_step = (time.time() - t0) / pasos

    perdidas, grads = historial(trainer)
    vram = torch.cuda.max_memory_allocated() / 1e9
    print("\n" + "=" * 60)
    print("Diagnostico del canario")
    print("  steps registrados : %d" % len(perdidas))
    print("  segundos por step : %.1f" % seg_step)
    print("  grad_norm         : min %.3f  max %.3f" % (min(grads), max(grads)))
    print("  perdida           : %s" % " -> ".join("%.2f" % p for p in perdidas))
    print("  VRAM pico         : %.2f GB" % vram)

    if vram > VRAM_LIMITE:
        print("\n  AVISO VRAM pico %.2f GB supera %.1f GB. Relanza con MAX_LEN=320." % (vram, VRAM_LIMITE))

    print("=" * 60)
    if all(g == 0 for g in grads):
        print("COMPUERTA 3: NO PASA - gradientes muertos (grad_norm=0 en los %d steps)." % len(grads))
        print("El entrenamiento correria sin aprender nada y sin dar error.")
        print("Verifica que use_reentrant=False este en AMBOS lugares:")
        print("  1) model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})")
        print("  2) SFTConfig(gradient_checkpointing_kwargs={'use_reentrant': False})")
        return 1

    if len(perdidas) < 6:
        print("COMPUERTA 3: NO PASA - muy pocos steps registrados para juzgar.")
        return 1

    inicio = sum(perdidas[:3]) / 3
    final = sum(perdidas[-3:]) / 3
    print("  media movil: inicio %.3f -> final %.3f (delta %+.3f)" % (inicio, final, final - inicio))
    if final >= inicio:
        print("COMPUERTA 3: PARCIAL - gradientes vivos (max %.3f) pero la perdida no baja." % max(grads))
        print("Accion: un reintento con LR=1e-4 python entrenar.py --canario")
        return 2

    # La prueba que faltaba: que el modelo ESCRIBA el formato, no solo que la
    # perdida baje. Con solo %d steps aun puede fallar, pero si a estas alturas
    # ni se acerca al formato, el completo tampoco va a servir.
    ok, texto = probar_formato(tok, model)
    if ok:
        print("COMPUERTA 3: PASA - gradientes vivos, perdida bajando y FORMATO CORRECTO.")
    elif texto.startswith("RIESGO:"):
        print("COMPUERTA 3: PASA (parcial) - empieza con 'RIESGO:' pero el formato aun no")
        print("esta completo. Con mas steps deberia cerrarse; lanzar completo.")
    else:
        print("COMPUERTA 3: NO PASA - la perdida baja pero el modelo NO produce el formato.")
        print("Sintoma de los dos entrenamientos fallidos anteriores. No lances el completo:")
        print("revisa que la mascara de labels sea correcta y que el prompt de entrenamiento")
        print("sea identico al de inferencia (add_generation_prompt=True).")
        return 1
    print("Tiempo estimado del completo: %.0f min" % (seg_step * 279 / 60))
    return 0


def completo():
    print(">>> MODO COMPLETO: 2 epochs sobre %s\n" % CORPUS)
    tok, model = cargar_modelo()
    data = cargar_datos(tok)
    salida = os.path.join(SALIDA_BASE, "checkpoints")
    # 3 epochs: con la perdida concentrada solo en la respuesta hay menos señal
    # por ejemplo, pero mucho mas util. lr_scheduler cosine con warmup corto.
    cfg = config_comun(salida, num_train_epochs=int(os.environ.get("EPOCHS", "3")),
                       save_strategy="steps", save_steps=50, save_total_limit=3,
                       warmup_ratio=0.03, lr_scheduler_type="cosine")
    trainer = crear_trainer(model, tok, data, cfg)
    t0 = time.time()
    trainer.train()
    minutos = (time.time() - t0) / 60

    destino = os.path.join(SALIDA_BASE, "adaptador-lora")
    trainer.save_model(destino)
    tok.save_pretrained(destino)
    # copia a la carpeta del proyecto para tenerlo a mano en Windows
    local = os.path.join(AQUI, "adaptador-lora")
    if os.path.exists(local):
        shutil.rmtree(local)
    shutil.copytree(destino, local)

    perdidas, grads = historial(trainer)
    print("\n" + "=" * 60)
    print("Entrenamiento terminado en %.1f min (%d steps)" % (minutos, len(perdidas)))
    print("  VRAM pico  : %.2f GB" % (torch.cuda.max_memory_allocated() / 1e9))
    print("  grad_norm  : min %.3f  max %.3f" % (min(grads), max(grads)))
    print("  adaptador  : %s" % destino)
    print("  copia local: %s" % local)
    print("\nCurva de perdida (1 punto cada 10 steps):")
    for i in range(0, len(perdidas), 10):
        bloque = perdidas[i:i + 10]
        print("  step %4d  %.4f" % (i + 1, sum(bloque) / len(bloque)))
    print("  perdida inicial %.4f -> final %.4f" % (perdidas[0], sum(perdidas[-5:]) / 5))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
        ax1.plot(range(1, len(perdidas) + 1), perdidas, linewidth=0.8, alpha=0.5, label="perdida")
        if len(perdidas) >= 10:
            suave = [sum(perdidas[max(0, i - 9):i + 1]) / len(perdidas[max(0, i - 9):i + 1])
                     for i in range(len(perdidas))]
            ax1.plot(range(1, len(suave) + 1), suave, linewidth=2, label="media movil (10)")
        ax1.set_ylabel("perdida"); ax1.legend(); ax1.grid(alpha=0.3)
        ax1.set_title("Chamba Segura - LoRA sobre Gemma 4 E2B (%d steps, %.1f min)" % (len(perdidas), minutos))
        ax2.plot(range(1, len(grads) + 1), grads, linewidth=0.8, color="tab:orange")
        ax2.set_ylabel("grad_norm"); ax2.set_xlabel("step"); ax2.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(AQUI, "perdidas.png"), dpi=120)
        print("\nGrafica guardada en perdidas.png")
    except ImportError as e:
        print("\nNo se genero la grafica (%s)" % e)

    print("\nSiguiente paso: python verificar_adaptador.py")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Entrenamiento LoRA de Chamba Segura")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--canario", action="store_true", help="20 steps de diagnostico (Compuerta 3)")
    g.add_argument("--completo", action="store_true", help="entrenamiento completo, 2 epochs")
    args = ap.parse_args()

    if not os.path.exists(CORPUS):
        print("FALTA %s. Corre generar_corpus.py primero." % CORPUS)
        sys.exit(1)
    os.makedirs(SALIDA_BASE, exist_ok=True)
    sys.exit(canario() if args.canario else completo())
