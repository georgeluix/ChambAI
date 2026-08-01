# Entrenamiento — pipeline de compuertas

Pipeline de fine-tuning LoRA de Gemma 4 E2B en una RTX 3070 Ti de 8 GB, con
compuertas de validación que interceptan fallos silenciosos. El resultado del
esfuerzo está documentado con honestidad: el adaptador aprende durante el
entrenamiento (pérdida 0.335 sobre la respuesta) pero no sobrevive a la
serialización (3.43 al recargar); la demo usa Gemma 4 base + few-shot vía
Ollama, decisión tomada con la evidencia de `evaluar_ollama.py`.

## Flujo

```
generar_corpus.py          corpus sintético; distribución derivada de 3 822
                           denuncias PNP 2017-2023 (../datos/datos_trata.json)
normalizar_avisos.py       normaliza avisos reales recolectados al catálogo
validar_pii.py             verifica ausencia de PII (regla 1.7 + Ley 29733)
mezclar_corpus.py          ensambla corpus.jsonl con trazabilidad por origen
        │
validar_corpus.py          COMPUERTA 1: estructura, formato, etiquetas,
                           duplicados, fuga corpus↔evaluación
inspeccionar_template.py   COMPUERTA 2: chat template de Gemma 4 renderizado
                           (marcadores <|turn> / <turn|>, orden de roles)
entrenar.py --canario      COMPUERTA 3: 60 steps; gradientes vivos, pérdida
                           bajando Y generación de prueba con formato correcto
entrenar.py --completo     entrenamiento (receta validada en receta.py)
verificar_adaptador.py     COMPUERTA 4: separa "terminó" de "sirvió"
evaluar_ollama.py          evaluación sobre 20 casos nunca vistos, contra el
                           stack real de la demo
```

## La receta (receta.py) — 4 fixes para Gemma 4 en 8 GB

1. **Sin `prepare_model_for_kbit_training`**: castea las torres multimodales a
   fp32 y pide 8.75 GiB inexistentes (OOM).
2. **`target_modules` como regex** `.*language_model.*`: `"all-linear"` choca
   con `Gemma4ClippableLinear` de la torre de visión (peft no lo soporta).
3. **`use_reentrant=False`** en el modelo Y en la config: sin esto grad_norm=0
   y el entrenamiento corre sin aprender, sin error.
4. **Tabla de embeddings per-layer a RAM**: bitsandbytes solo cuantiza capas
   Linear; la tabla per-layer de Gemma 4 (262 144 × 8 960) son 4.7 GB en bf16
   que nunca se cuantizan. Con el lookup en CPU el modelo pasa de 6.94 a
   2.16 GB de VRAM y el pico de entrenamiento queda en 6.86 GB.

## Los seis fallos silenciosos (ninguno lanzó una excepción)

| # | Fallo | Cómo se detectó |
|---|---|---|
| 1 | OOM por cast fp32 de torres multimodales | smoke test nocturno |
| 2 | peft vs `Gemma4ClippableLinear` | smoke test nocturno |
| 3 | Gradientes muertos (reentrant checkpointing) | smoke test (grad_norm=0) |
| 4 | 4.7 GB de embeddings sin cuantizar | diagnóstico de VRAM por dtype |
| 5 | `completion_only_loss` de TRL enmascaró el 99% del texto como "respuesta" | inspección del `completion_mask` real |
| 6 | Adaptador con pérdida 0.335 rinde 3.43 al recargar | Compuerta 4 + medición teacher-forcing |

El fallo 5 significa que la pérdida entrenaba sobre el texto del aviso en vez
de la respuesta: métricas verdes (accuracy 0.91), modelo respondiendo markdown
genérico. La máscara se reconstruyó a mano en `cargar_datos()` con el prompt
construido **idéntico al de inferencia** (`add_generation_prompt=True`).

El fallo 6 queda abierto: los checkpoints intermedios (ruta de guardado
distinta) rinden igual que el final, así que la discrepancia está entre el
forward del Trainer y el de inferencia, no en la serialización misma.

## Datos

- `corpus.jsonl` — 370 ejemplos (40% alto / 30% medio / 30% bajo), cada línea
  con campo `origen`: 330 sintéticos propios, 25 reales anonimizados y
  trazables por URL, 15 sintéticos externos.
- `evaluacion.jsonl` — 20 casos escritos a mano con redacción real de redes
  (emojis, faltas de ortografía). Nunca entraron a ningún corpus; la
  Compuerta 1 verifica la ausencia de fuga.
- `avisos-reales-crudo.jsonl` — los 30 recolectados originales (5 descartados
  del entrenamiento por ser crónicas/campañas, no avisos).
- `resultados-evaluacion-ollama.json` — resultados crudos de la evaluación.

## Reproducir

```bash
source ~/venv-hackathon/bin/activate
python generar_corpus.py && python mezclar_corpus.py
python validar_corpus.py && python inspeccionar_template.py
python entrenar.py --canario        # ~4 min
python entrenar.py --completo       # ~20 min
python verificar_adaptador.py
python evaluar_ollama.py            # requiere Ollama con gemma4:e2b
```
