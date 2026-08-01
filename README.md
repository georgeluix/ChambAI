# ChambAI — Chamba Segura

Aplicacion local que analiza texto o fotografias de avisos laborales y explica
senales preventivas de captacion riesgosa. El resultado es orientativo: no
determina delitos ni reemplaza a las autoridades.

## Estructura

```text
backend/    FastAPI, LangGraph, reglas y cliente de Ollama
datos/      estadisticas agregadas PNP-MININTER usadas en runtime
frontend/   React + Vite
docs/       arquitectura, contrato de API y estado
```

El entrenamiento se mantiene fuera de este commit mientras el proceso esta
activo. La aplicacion funciona con `gemma4:e2b` base y few-shot.

## Como funciona

Gemma trabaja una vez para texto y dos veces para una imagen:

```text
Frontend -> FastAPI -> LangGraph -> Ollama (Gemma 4 E2B local)

1. extraer         imagen -> Gemma vision transcribe literalmente
2. reglas          codigo: menores/cobros fuerzan riesgo alto
3. analizar        texto -> Gemma few-shot -> texto plano estructurado
4. contextualizar  datos_trata.py -> estadistica real del departamento
5. consolidar      las reglas prevalecen -> JSON para el frontend
```

Gemma nunca genera el JSON final ni inventa estadisticas. El backend parsea su
salida `RIESGO/BANDERAS/EXPLICACION`, aplica reglas verificables y agrega cifras
del dataset local. Cada bandera conserva `origen: modelo|regla`.

## Ejecutar en local

Ollama vive en Windows y FastAPI en WSL. Con Ollama ya iniciado en Windows:

```bash
# WSL, desde la raiz del repositorio
source ~/venv-hackathon/bin/activate
cd backend
bash iniciar-wsl.sh
```

En PowerShell:

```powershell
cd frontend
npm ci
npm run dev:api
```

Abre `http://localhost:5173`. No lances un analisis mientras otro proceso este
entrenando en la misma GPU.

## Contratos criticos

- Ollama: `POST /api/chat`, `think:false`, `num_ctx:16384`.
- WSL a Ollama Windows: `OLLAMA_URL=http://172.26.176.1:11434`.
- Texto: `POST /api/analizar` con `{ "texto": "..." }`.
- Imagen: `POST /api/analizar-imagen`, multipart campo `archivo`.
- Frontend: `VITE_API_URL=http://localhost:8000`.

Consulta [docs/CONTRATO_API.md](docs/CONTRATO_API.md) para la respuesta completa.

## Verificar sin usar la GPU

```bash
cd backend
python -m unittest discover -p "test_*.py" -v
cd ../frontend
npm run build
```

Las pruebas reemplazan Ollama por respuestas en memoria. No cargan Gemma.

## Privacidad

El análisis ocurre localmente. El backend no registra el aviso ni la imagen;
solo registra el nivel y el tiempo. Para riesgo alto recomienda la Linea 1818
del MININTER.
