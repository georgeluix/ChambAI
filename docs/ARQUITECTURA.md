# Arquitectura

## Flujo LangGraph

```text
Usuario
  |
  v
React/Vite (:5173)
  |
  v
FastAPI (:8000)
  |
  v
extraer -> reglas -> analizar -> contextualizar -> consolidar
  |          |          |             |                |
  |          |          |             |                `-> JSON final
  |          |          |             `-> datos PNP locales
  |          |          `-> Gemma texto, few-shot
  |          `-> reglas legales deterministas
  `-> Gemma vision, solo cuando la entrada es imagen
```

## Division de responsabilidades

- Gemma vision transcribe literalmente; no interpreta la imagen.
- Gemma texto clasifica con un catalogo cerrado y devuelve texto plano.
- Python fuerza las reglas que no pueden depender del modelo.
- `datos/datos_trata.py` aporta cifras agregadas verificables.
- El consolidado deduplica banderas, calcula puntaje y prioriza reglas.
- React diferencia visualmente `origen=modelo` y `origen=regla`.

## Ollama

FastAPI usa `POST /api/chat`. `think:false` evita que Gemma 4 entregue el
contenido util en el canal de razonamiento, y cada llamada fija explícitamente
`num_ctx=16384`. Las inferencias se serializan para proteger la VRAM.

En el entorno de demo Ollama corre en Windows y FastAPI en WSL, por eso uvicorn
se inicia con `OLLAMA_URL=http://172.26.176.1:11434`.

Una solicitud de texto hace una llamada a Gemma. Una imagen hace dos llamadas
secuenciales: vision y luego clasificacion del texto transcrito.

## Seguridad

- JPG, PNG y WEBP hasta 10 MB; se valida la firma real del archivo.
- Sin logs de texto, imagenes ni telefonos.
- CORS limitado a los origenes configurados.
- Reintento unico ante formato invalido.
- Etiquetas fuera del catalogo no suman puntaje ni llegan a la interfaz.
