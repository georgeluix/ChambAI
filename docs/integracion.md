# Cómo funciona Chamba Segura con Gemma 4 — guía de integración

Para backend y frontend: qué hace cada pieza, qué viaja por cada llamada y qué
tiene que conectar cada uno. Leer junto con `arranque-demo.md` (comandos).

## La arquitectura en una imagen

```
[React :5173]
     │  POST /api/analizar {"texto": ...}
     │  POST /api/analizar-imagen (multipart, campo "archivo")
     │  GET  /api/estadisticas   GET /api/salud
     ▼
[FastAPI :8000  (WSL)]
     ▼
[Grafo LangGraph — 5 nodos]
  1 extraer ──── si es imagen → GEMMA 4 (visión) transcribe el texto literal
  2 reglas ───── código puro: menores de edad / cobros → fuerzan "alto"
  3 analizar ─── GEMMA 4 (texto) clasifica con few-shot → RIESGO/BANDERAS/EXPLICACION
  4 contextualizar ─ datos_trata.py: estadísticas reales del departamento mencionado
  5 consolidar ─ regla gana sobre modelo, une banderas, arma el JSON final
     ▼
[Ollama :11434 (Windows) — gemma4:e2b, 100% local, sin internet]
```

Gemma 4 E2B es el núcleo y trabaja **dos veces** por análisis de imagen y una
por análisis de texto:

- **Rol 1 — Visión (nodo extraer):** recibe la captura de pantalla y transcribe
  el texto del aviso tal cual (faltas de ortografía y emojis incluidos). No
  interpreta. Si la imagen no contiene un aviso responde `SIN_AVISO` y la API
  devuelve `aviso_detectado: false` (HTTP 200, no error).
- **Rol 2 — Análisis (nodo analizar):** recibe el texto (pegado o transcrito)
  con un prompt few-shot de 3 ejemplos (alto/medio/bajo) y el catálogo de 21
  banderas. Responde SIEMPRE en el formato de texto plano:

  ```
  RIESGO: alto
  BANDERAS:
  - Traslado fuera de la ciudad con pasaje cubierto por el empleador
  - Alojamiento dentro del centro de trabajo
  EXPLICACION: dos o tres oraciones, en alto siempre cita la Linea 1818.
  ```

  El backend parsea ese formato con regex y lo convierte a JSON. El modelo
  NUNCA devuelve JSON directamente (evaluado: 100% parseable en 20 casos).

Lo que Gemma NO hace: las estadísticas. Los números (72.9%, denuncias por
departamento) salen de `datos/datos_trata.json`, procesado del dataset PNP
2017-2023. El modelo no memoriza cifras → no puede alucinarlas; se citan
exactas desde el archivo.

Lo que Gemma NO decide sola: menores de edad y cobros al postulante. Son reglas
en código (nodo 2) que fuerzan riesgo alto aunque el modelo diga otra cosa.
Cada bandera lleva `origen: "modelo"` u `origen: "regla"` — el frontend DEBE
mostrarlos distinto (es el argumento de transparencia del pitch).

## PARA EL BACKEND — 3 cosas ya aplicadas, no revertir

1. **`/api/chat`, no `/api/generate`** (modelo.py línea ~135). Gemma 4 es un
   modelo con thinking: por generate toda su salida cae al campo `thinking` y
   `response` llega vacío → 41 s y análisis fallido. Por chat con
   `"think": false` → 1.7 s y formato válido. Ya está corregido en modelo.py;
   si tienes copia local, sincroniza.
2. **`OLLAMA_URL=http://172.26.176.1:11434`** al arrancar uvicorn. Ollama corre
   en Windows y WSL no ve `localhost`. La IP es el gateway de WSL
   (`ip route show default | awk '{print $3}'` si cambió tras reiniciar).
   Ollama debe arrancarse con `OLLAMA_HOST=0.0.0.0:11434` (ver arranque-demo.md).
3. **Toda llamada lleva `num_ctx: 16384`** en options (regla del equipo) y
   `temperature: 0` para el análisis.

Pendiente recomendado (2 min): en el fallback de formato inválido, devolver
`riesgo: "medio"` con mensaje de "no se pudo analizar" — nunca `"bajo"`.

## PARA EL FRONTEND — contrato exacto

Config: `VITE_API_URL=http://localhost:8000`. CORS ya permite `:5173`.

**Enviar:**
- Texto: `POST {API}/api/analizar` body `{"texto": "..."}`
- Imagen: `POST {API}/api/analizar-imagen`, multipart, campo **`archivo`**
  (jpg/png/webp, máx 10 MB)

**Recibir (ambos endpoints, misma forma):**

```json
{
  "riesgo": "alto",                  // pinta el semáforo: bajo|medio|alto
  "puntaje": 70,                     // 0-100, para la barra
  "banderas": [
    {"texto": "Alojamiento dentro del centro de trabajo",
     "gravedad": "grave",            // grave | critica | leve → color/icono
     "origen": "modelo"}             // modelo | regla → badge distinto
  ],
  "explicacion": "…",
  "recomendacion": "… Linea 1818 …", // en alto, mostrarla destacada
  "contexto_local": {
    "departamentos_mencionados": ["CUSCO"],
    "frases": ["Cusco registra 187 denuncias de trata (2017-2023), …"]
  },                                 // mostrar como cita con fuente PNP/MININTER
  "texto_analizado": "…",            // en imagen: transcripción → mostrarla
                                     // EDITABLE y permitir re-analizar
  "aviso_detectado": true,           // false = la imagen no era un aviso
  "formato_valido": true,            // false = mostrar aviso de análisis parcial
  "tiempo_ms": 1694
}
```

- Panel de estadísticas: `GET /api/estadisticas` (ficha nacional + top 10
  departamentos, para gráficos).
- Salud: `GET /api/salud` → si `ollama: false`, mostrar "modelo local no
  disponible" en vez de romper.
- Tiempos reales: texto ~2-6 s; imagen ~8-15 s (dos pasadas de Gemma).
  Poner un estado de carga con mensaje ("Gemma 4 está leyendo el aviso…").

## Los números que respaldan todo (para el pitch y el writeup)

- 20 casos de evaluación nunca vistos: **85% exactitud, 0 omisiones de riesgo
  alto (8/8 peligrosos detectados), 0 confusiones alto↔bajo, 100% parseable,
  117 tok/s** en la RTX 3070 Ti de 8 GB.
- Los 3 errores fueron medio→alto: el sistema se equivoca hacia la cautela.
- 72.9% de las denuncias de trata (PNP 2017-2023) empezaron con una falsa
  oferta de trabajo — calculado en el repo, corroborado por Ministerio Público.
