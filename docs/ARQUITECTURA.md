# Arquitectura de ChambAI

## Objetivo

Recibir el texto de un aviso laboral, analizarlo en el mismo equipo y devolver señales comprensibles de posible captación fraudulenta. La aplicación no califica jurídicamente una conducta ni acusa a una persona o empresa.

## Principios del proyecto

1. **Privacidad local:** los avisos no salen del equipo.
2. **Explicabilidad:** cada alerta incluye tipo, descripción y fragmento del aviso.
3. **Lenguaje responsable:** se comunica riesgo, no culpabilidad.
4. **Simplicidad:** se prioriza una demo estable dentro de un hackathon de cinco horas.
5. **Accesibilidad:** alto contraste, letras legibles y diseño adaptable a celular.

## Componentes

```text
Usuario
  │
  ▼
React + Vite (:5173)
  │ POST /analyze o /analyze-image
  ▼
FastAPI (:8000)
  │
  ▼
LangGraph
  │
  ▼
Ollama local + Gemma 4 E2B
```

No debe haber APIs, fuentes, tipografías, telemetría ni otros recursos remotos necesarios durante la ejecución.

## Frontend

Ubicación actual: `src/`.

Responsabilidades:

- Capturar el aviso laboral.
- Tomar o elegir una foto y enviarla al backend local.
- Enviar `{ "texto": "..." }` al endpoint local.
- Mostrar carga, error o resultado.
- Representar el nivel de riesgo mediante color y texto.
- Mostrar las banderas y sus fragmentos.
- Presentar explicación y disclaimer.

El color nunca debe ser el único medio para comunicar el riesgo.

### Flujo de fotografías

```text
cámara o galería → previsualización → POST /analyze-image → OCR y análisis en backend
```

No se aceptan URL de imágenes. La fotografía se envía como `multipart/form-data` en un campo llamado `imagen`. El backend devuelve el mismo esquema de resultado que el análisis de texto.

## Backend

Tecnología fijada: FastAPI.

Responsabilidades previstas:

- Validar que `texto` no esté vacío.
- Validar la imagen y ejecutar OCR local para `POST /analyze-image`.
- Ejecutar el grafo de análisis.
- Normalizar y validar la salida del modelo.
- Devolver siempre el contrato acordado.
- Permitir CORS únicamente para los orígenes locales necesarios durante el desarrollo.
- Entregar errores controlados sin exponer trazas internas.

Endpoint acordado: `POST /analyze`.

## Orquestación

Tecnología fijada: LangGraph.

Para el MVP conviene un flujo corto:

```text
validar entrada → analizar aviso → validar/normalizar JSON → responder
```

Solo se deben añadir nodos adicionales si aportan estabilidad demostrable. El flujo debe poder probarse con ejemplos deterministas sin conexión a internet.

## Modelo local y Ollama

Modelo fijado por el equipo: Gemma 4 E2B ejecutado localmente mediante Ollama.

Regla obligatoria para toda conexión o invocación:

```python
num_ctx = 16384
```

Esta opción no debe depender del valor predeterminado de Ollama. Debe aparecer explícitamente en la configuración de cada cliente o invocación.

Antes de cerrar la integración, se debe confirmar el identificador exacto del modelo instalado mediante `ollama list`, porque el nombre usado por Ollama debe coincidir literalmente.

## Contrato de datos

Entrada:

```json
{ "texto": "..." }
```

Salida:

```json
{
  "riesgo": "bajo | medio | alto",
  "banderas": [
    {
      "tipo": "string",
      "descripcion": "string",
      "fragmento": "string"
    }
  ],
  "explicacion": "string",
  "disclaimer": "string"
}
```

Los nombres de campos forman parte del contrato y no deben traducirse ni modificarse. El backend debe validar la salida estructurada antes de enviarla al frontend.

## Seguridad y comunicación responsable

- No afirmar que una oferta es un delito como conclusión automática.
- No presentar al modelo como una autoridad.
- No inventar teléfonos, entidades, estadísticas ni rutas de denuncia.
- Verificar cualquier información institucional antes de incorporarla a la interfaz final.
- Evitar registrar el texto completo de los avisos en producción o durante la demo.
- No cargar fotos ni ejecutar OCR mediante servicios externos.
- Mantener visible el disclaimer en cada resultado.

## Decisiones pendientes

- Confirmar el identificador exacto del modelo disponible en Ollama.
- Definir el esquema Pydantic del backend.
- Definir el prompt de análisis y ejemplos de prueba.
- Decidir si el MVP usará una sola llamada al modelo o validación/reintento local.
- Verificar fuentes institucionales y canales de ayuda que se mostrarán.
- Definir la estrategia de distribución móvil. El stack Ollama/FastAPI requiere un equipo servidor local y no convierte por sí solo el teléfono en un dispositivo autónomo.
