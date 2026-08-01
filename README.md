# ChambAI

Aplicación local para analizar avisos de trabajo e identificar señales de posible captación fraudulenta vinculada a la trata de personas en Perú.

> Proyecto de hackathon. El sistema orienta sobre señales de riesgo; no determina delitos ni reemplaza la evaluación de autoridades o especialistas.

## Propuesta de valor

- El análisis funciona completamente en el equipo del usuario.
- El texto del aviso no se envía a servicios externos.
- Las fotos se envían únicamente al backend local encargado del OCR y análisis.
- La interfaz explica las señales encontradas en lenguaje claro.
- Está pensada para una demostración simple, rápida y usable desde celular.

## Arquitectura

- Frontend: React + Vite.
- Backend: FastAPI.
- Orquestación: LangGraph.
- Modelo local: Gemma 4 E2B mediante Ollama.
- Contexto obligatorio de Ollama: `num_ctx=16384` en todas las llamadas.

Consulta [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para el diseño y las decisiones técnicas.

## Estado actual

El frontend de una sola pantalla está implementado. Incluye formulario, conexión al backend, semáforo de riesgo, banderas, explicación, aviso legal y estados de carga y error.

La interfaz permite tomar/elegir una foto o pegar el texto recibido. No acepta enlaces como fuente de imágenes.

El backend y la integración con Ollama/LangGraph todavía no están implementados en este repositorio.

Consulta [docs/ESTADO.md](docs/ESTADO.md) antes de comenzar o continuar trabajo.

## Ejecutar el frontend

Requisitos:

- Node.js 20 LTS o una versión compatible.
- npm.

```bash
npm install
npm run dev
```

`npm run dev` utiliza respuestas simuladas locales para que el frontend pueda desarrollarse sin el backend. Para conectarlo con FastAPI usa:

```bash
npm run dev:api
```

Vite normalmente abrirá la aplicación en `http://localhost:5173`. En modo API, el backend deberá ejecutarse en `http://localhost:8000` y permitir CORS desde el origen de Vite. El build de producción siempre utiliza la API real.

## Probar una foto

En `npm run dev`, abre la pestaña `Tomar foto`, elige una imagen legible y presiona `Analizar foto`. El modo demo simula una respuesta de riesgo alto sin procesar realmente la imagen.

En `npm run dev:api`, el frontend envía la imagen al backend local. El backend será responsable del OCR y del análisis.

## Alcance móvil y offline

El frontend está diseñado primero para teléfono y puede usar la cámara mediante el selector de archivos del dispositivo. En una computadora se muestra centrado con ancho de app móvil de forma intencional.

La interfaz no necesita internet. El OCR y el análisis necesitan alcanzar el equipo local donde se ejecuten FastAPI, LangGraph y Ollama. Para una demo desde teléfono, ambos dispositivos deben compartir una red local y el backend debe exponer su dirección dentro de esa red. Ejecutar el modelo completamente dentro de un teléfono requeriría una arquitectura distinta al stack actual.

## Contrato con el backend

El frontend realiza:

```http
POST http://localhost:8000/analyze
Content-Type: application/json
```

Solicitud:

```json
{
  "texto": "Texto completo del aviso laboral"
}
```

Respuesta exacta esperada:

```json
{
  "riesgo": "bajo",
  "banderas": [
    {
      "tipo": "Solicitud de dinero",
      "descripcion": "La oferta solicita un pago previo.",
      "fragmento": "Deposita S/ 50 para separar tu vacante"
    }
  ],
  "explicacion": "La solicitud de pagos previos es una señal de riesgo.",
  "disclaimer": "Este análisis es orientativo y no constituye una denuncia ni una determinación legal."
}
```

Valores admitidos para `riesgo`: `bajo`, `medio` o `alto`. `banderas` siempre debe ser una lista, incluso si está vacía.

Para fotografías, el frontend realiza:

```http
POST http://localhost:8000/analyze-image
Content-Type: multipart/form-data
```

El formulario contiene un único campo llamado `imagen`. La respuesta utiliza exactamente el mismo esquema JSON que `/analyze`.

## Continuar después de reiniciar

1. Abre esta carpeta en tu editor o en Codex.
2. Lee [docs/ESTADO.md](docs/ESTADO.md).
3. Verifica las herramientas con `node --version`, `npm --version`, `python --version` y `ollama --version`.
4. Inicia el componente en el que estés trabajando.
5. Actualiza `docs/ESTADO.md` al terminar una sesión relevante.

Si abres otro chat, puedes usar este mensaje:

> Estamos continuando el proyecto ChambAI. Revisa README.md, docs/ARQUITECTURA.md y docs/ESTADO.md antes de modificar archivos. Respeta el contrato de la API, el funcionamiento offline y usa siempre num_ctx=16384 al conectar con Ollama.

## Información preliminar

Como contexto del hackathon se proporcionó el dato preliminar de que el 74 % de las víctimas fueron captadas mediante falsas ofertas, atribuido a MININTER. Debe verificarse la fuente exacta antes de presentarlo como cifra oficial o publicarlo.
