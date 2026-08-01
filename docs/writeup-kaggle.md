# Chamba Segura — detección local de falsas ofertas de trabajo vinculadas a trata de personas

**Subtítulo:** Gemma 4 E2B corriendo 100% local analiza avisos de empleo peruanos y explica, con datos abiertos del Estado, por qué una oferta es peligrosa — sin que el aviso salga jamás de tu equipo.

**Track:** AI for Social Impact · ODS 5 (Igualdad de género) y ODS 1 (Fin de la pobreza)
**Equipo SOINAR:** Abel Mancilla, Jorge Cruzado, Frank Chuctaya

---

## El problema, calculado desde la fuente primaria

En el Perú, la puerta de entrada a la trata de personas no es el secuestro: es un aviso de trabajo. Procesamos el dataset público de denuncias de trata de la PNP (Datos Abiertos del Estado Peruano, 180 600 registros, 2017–2023) y el resultado es contundente: **de 3 822 denuncias con vía de captación registrada, el 72.9% empezó con una falsa oferta de trabajo**. No citamos ese número de un informe — lo calcula `datos/procesar_dataset.py` en nuestro repo, reproducible línea por línea. El Ministerio Público lo corrobora de forma independiente: 73.8% en el primer semestre de 2023.

El mismo dataset dibuja a quién ataca este delito: 86.2% de las víctimas son mujeres, el 85.7% de ellas tiene entre 12 y 29 años, y el 75.6% alcanzó como máximo secundaria. El medio dominante es el engaño (60.2%), y en departamentos como Madre de Dios —minería ilegal— el 91.3% de las denuncias comenzaron con una oferta laboral.

Quien sospecha de un aviso hoy no tiene dónde verificarlo. Chamba Segura le da una respuesta en segundos, explicada y con el dato local que respalda la alerta.

## Qué hace

El usuario pega el texto de un aviso — o sube la captura de pantalla de Facebook/WhatsApp, que es como circulan realmente — y recibe:

- **RIESGO: bajo / medio / alto**
- **BANDERAS:** señales concretas detectadas, de un catálogo de 21 indicadores construido sobre las modalidades documentadas por MININTER (filtro por apariencia, traslado con pasaje pagado, retención de DNI, cobros al postulante, exigencia de secreto frente a la familia…)
- **EXPLICACIÓN** en lenguaje claro, y en riesgo alto, la recomendación de reportar a la **Línea 1818** del MININTER
- **Contexto local:** si el aviso menciona un lugar ("viaje a Puerto Maldonado"), el sistema responde con la estadística real de ese departamento

## Cómo usamos Gemma 4 (y por qué es el núcleo)

Gemma 4 E2B corre **local en Ollama** (num_ctx=16384) sobre una laptop con RTX 3070 Ti de 8 GB. Es el corazón del sistema en dos roles:

1. **Extracción multimodal:** un modelo de visión de la familia Gemma transcribe el texto del aviso desde la captura, literal, con faltas de ortografía y emojis. La torre de visión de Gemma 4 resultó rota en la build actual de Ollama (reto 7, abajo), así que el OCR corre en Gemma 3 4B; la visión solo lee, nunca decide. El usuario puede corregir la transcripción antes de analizar — auditable por diseño.
2. **Análisis:** el transformer de texto de Gemma 4 E2B clasifica el riesgo y argumenta las banderas con few-shot sobre nuestro catálogo.

Alrededor del modelo, un grafo de **LangGraph** orquesta cinco nodos (extraer → reglas → analizar → contextualizar → consolidar) detrás de **FastAPI**, con frontend en **React**. Dos decisiones de arquitectura importan:

- **Reglas deterministas por encima del modelo.** La convocatoria a menores de edad y el cobro al postulante fuerzan riesgo alto por código, no por patrón aprendido: el Art. 153 del Código Penal consuma el delito con la sola captación del menor, y una línea legal así no puede depender de probabilidades. Cada bandera lleva su origen (`modelo` o `regla`) visible en la interfaz.
- **Privacy-first en serio.** Todo corre sin internet; el backend no persiste ningún aviso analizado. Coherente con la Ley 29733, la misma norma que protege a las víctimas cuyos datos este delito explota.

## Datos abiertos como calibración, no como decoración

El dataset de la PNP no contiene texto de avisos — son conteos. Lo usamos donde sí aporta:

- **En inferencia:** un módulo compacto (`datos_trata.py`, JSON de 49 KB, cero dependencias) detecta departamentos mencionados en el aviso y devuelve sus cifras reales. El modelo nunca memoriza estadísticas: se citan desde la fuente, exactas.
- **En los datos de entrenamiento:** generamos un corpus sintético cuya distribución de señales **se deriva de las frecuencias reales de las 3 822 denuncias** — engaño 60.2%, night club y prostíbulo como principales lugares de explotación, destinos ponderados por denuncias con captación laboral. Lo mezclamos con 25 avisos reales recolectados de clasificados y portales peruanos, anonimizados (verificador de PII incluido en el repo) y trazables por URL. Cada línea del corpus lleva su campo `origen`.

Decidimos **no** recolectar masivamente avisos reales de captación: publicar teléfonos y nombres en un repo público violaría la regla 1.7 de la competencia y la Ley 29733, y compilar un directorio de canales activos de captación es un daño en sí mismo. El corpus sintético calibrado con datos oficiales es la alternativa éticamente defendible — y reproducible.

## Los retos: seis fallos silenciosos y un pipeline de compuertas

Intentamos fine-tunear Gemma 4 E2B con LoRA en los 8 GB de la laptop. Construimos un pipeline con compuertas de validación (datos → template → canario → adaptador) porque solo había tiempo para un entrenamiento. Terminó interceptando **siete fallos, ninguno de los cuales lanzó un error**:

1. `prepare_model_for_kbit_training` castea las torres multimodales a fp32 → OOM instantáneo.
2. `target_modules="all-linear"` choca con `Gemma4ClippableLinear` de la torre de visión, que peft no soporta.
3. Sin `use_reentrant=False`, grad_norm=0: el entrenamiento "corre" sin aprender nada.
4. bitsandbytes no cuantiza embeddings: la tabla per-layer de Gemma 4 (262 144 × 8 960) son **4.7 GB en bf16 invisibles** que dejaban 0.5 GB libres. La movimos a RAM con un lookup en CPU (modelo: 6.94 → 2.16 GB).
5. `completion_only_loss` de TRL reportaba máscara aplicada, pero cubría el 99% de los tokens — la pérdida entrenaba sobre el aviso, no sobre la respuesta. Lo detectamos inspeccionando el `completion_mask` real y reconstruimos la máscara a mano.
6. El adaptador entrenado (pérdida 0.335) rinde 3.43 al recargarse desde disco — el aprendizaje no sobrevive a la serialización. Checkpoints intermedios idénticos: el fallo está en la discrepancia entrenamiento/inferencia del stack, no en el guardado.
7. La visión de Gemma 4 en la build actual de Ollama devuelve basura ("A A A A", `SIN_TEXTO`) ante afiches perfectamente legibles — verificado en e2b y e4b, por dos endpoints, con y sin thinking. Gemma 3 4B transcribe el mismo afiche completo en 12 s: el OCR se movió ahí y el análisis siguió en Gemma 4.

Con el fallo 6 sin resolver a dos horas del cierre, aplicamos la regla que habíamos pre-acordado: **few-shot sin discusión**. La Compuerta 4 ("¿terminó?" ≠ "¿sirvió?") evitó cuatro veces que integráramos un adaptador que generaba markdown genérico con métricas de entrenamiento en verde. Ese pipeline de compuertas, con timestamps y logs, está completo en el repo.

## Evaluación honesta

20 casos escritos a mano con redacción real de redes sociales (emojis, mayúsculas, faltas de ortografía), disjuntos de todo corpus — la Compuerta 1 verifica la ausencia de fuga. Resultados del stack de la demo (Gemma 4 E2B + few-shot vía Ollama, **sin** contar las reglas deterministas que solo pueden mejorar el resultado):

| Métrica | Resultado |
|---|---|
| Exactitud de RIESGO | **85%** (17/20) |
| Omisiones de riesgo alto (el error que importa) | **0 de 8** — ningún aviso peligroso subestimado |
| Confusiones alto↔bajo | 0 |
| Formato parseable | 100% (20/20) |
| Velocidad | **117 tok/s** en una GPU de laptop de 8 GB (~6 s por análisis) |

Los 3 errores son del mismo tipo: casos ambiguos clasificados `medio → alto`. Para una herramienta de protección, equivocarse hacia la cautela es la dirección correcta del error — lo inaceptable sería lo inverso, y ocurrió cero veces. El script (`evaluar_ollama.py`) y los resultados crudos están en el repo.

## Por qué estas decisiones fueron las correctas

Un E2B local no es una limitación: es el requisito. La población objetivo —mujeres jóvenes, en provincias, con conectividad intermitente— no puede depender de una API de pago, y un aviso sospechoso es exactamente el tipo de dato que no debería subirse a la nube. Gemma 4 E2B es hoy el único modelo abierto que combina visión nativa, español fluido y 8 GB de VRAM. La honestidad del intento de fine-tune —documentado, medido y descartado con evidencia— vale más que un adaptador maquillado: el sistema que presentamos es el que de verdad funciona.

## Próximos pasos

Resolver la serialización del adaptador (issue documentado), empaquetar como app de escritorio sin instalación técnica, y llevar el catálogo de banderas a validación con CHS Alternativo y la Dirección contra la Trata de la PNP.

---

*Repositorio público y demo adjuntos. Fuentes: Datos Abiertos del Estado Peruano (dataset 6522273, PNP/MININTER 2017-2023); Informe de la Política Nacional frente a la Trata de Personas, I semestre 2023.*
