# -*- coding: utf-8 -*-
"""Receta de carga de Gemma 4 E2B en 8 GB de VRAM. Validada en hardware.

La usan entrenar.py y verificar_adaptador.py: si divergen, el adaptador se
entrena sobre una configuracion y se sirve sobre otra.

CUATRO FIXES, EN ORDEN DE DESCUBRIMIENTO:

1. SIN prepare_model_for_kbit_training. Castea a fp32 las torres multimodales
   y pide 8.75 GiB que no existen -> OOM instantaneo. Se reemplaza por las
   tres lineas manuales de preparar().

2. target_modules como REGEX sobre language_model. "all-linear" choca con
   Gemma4ClippableLinear de la torre de vision, que peft no soporta.

3. use_reentrant=False en el modelo Y en SFTConfig. Sin esto grad_norm queda
   en 0 y el entrenamiento corre en el vacio SIN dar ningun error.

4. embed_tokens_per_layer a CPU (este). bitsandbytes solo cuantiza capas
   Linear, no Embedding. Gemma 4 usa per-layer inputs (256 dims x 35 capas =
   8960) sobre un vocab de 262144: son 4.7 GB en bf16 que NUNCA se cuantizan.
   Por eso el modelo pesaba 6.94 GB y dejaba 0.50 GB libres, insuficiente para
   los logits del calculo de la perdida (vocab 262144 -> ~1.5 GB por forward).
   Con la tabla en RAM el modelo baja a 2.16 GB y el pico a ~6.9 GB.
   El lookup en CPU cuesta ~0.05 s por forward: irrelevante frente al OOM.

   No se usa el offload de accelerate (device_map con "cpu") porque sus hooks
   suben la tabla entera a la GPU en cada forward: el pico vuelve a 6.98 GB.
"""
import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch  # noqa: E402
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig  # noqa: E402

MODELO = os.environ.get("MODELO_BASE", "/home/abel_brayan/gemma-4-e2b")
# p95 del corpus = 292 tokens, maximo 311 (Compuerta 1). 384 no trunca nada y
# ademas garantiza que nunca se pida un forward de 512, que si desborda.
MAX_LEN = int(os.environ.get("MAX_LEN", "384"))
PATRON_LORA = r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)"


def cargar_base(verboso=True):
    """Devuelve (tokenizer, modelo_4bit) con la tabla per-layer ya en RAM."""
    tok = AutoTokenizer.from_pretrained(MODELO)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_quant_type="nf4")
    model = AutoModelForCausalLM.from_pretrained(MODELO, quantization_config=bnb,
                                                 device_map={"": 0})
    if verboso:
        print("Modelo cargado: %.2f GB de VRAM" % (torch.cuda.memory_allocated() / 1e9))

    # FIX 4: la tabla de embeddings per-layer (4.7 GB bf16) vive en RAM
    emb = model.model.language_model.embed_tokens_per_layer
    peso_cpu = emb.weight.data.to("cpu")
    escala = emb.embed_scale.detach().to("cpu").to(peso_cpu.dtype)
    relleno = emb.padding_idx

    # El parametro del modulo queda VACIO a proposito: el Trainer llama
    # model.to(device) y volveria a subir los 4.7 GB a la VRAM. Con el peso solo
    # en el closure, ningun .to() posterior puede reintroducirlo.
    emb.weight = torch.nn.Parameter(torch.empty(0, dtype=peso_cpu.dtype), requires_grad=False)
    torch.cuda.empty_cache()

    def _lookup_en_cpu(input_ids, *a, **kw):
        salida = torch.nn.functional.embedding(input_ids.to("cpu"), peso_cpu, relleno)
        return (salida * escala).to(0)

    emb.forward = _lookup_en_cpu
    if verboso:
        print("Tabla per-layer (%.2f GB) movida a RAM: %.2f GB de VRAM"
              % (peso_cpu.numel() * peso_cpu.element_size() / 1e9,
                 torch.cuda.memory_allocated() / 1e9))
    return tok, model


def preparar(model):
    """Reemplazo manual de prepare_model_for_kbit_training (FIX 1 y 3)."""
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    for nombre, p in model.named_parameters():
        if any(t in nombre.lower() for t in ["vision", "audio", "image"]):
            p.requires_grad = False
    return model


def envolver_lora(model, r=16, alpha=32, dropout=0.05):
    """Aplica LoRA solo al transformer de texto (FIX 2)."""
    from peft import LoraConfig, get_peft_model
    lora = LoraConfig(r=r, lora_alpha=alpha, target_modules=PATRON_LORA,
                      lora_dropout=dropout, task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()
    return model
