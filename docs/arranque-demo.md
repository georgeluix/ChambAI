# Arranque de la demo — Chamba Segura

Si algo se cae antes o durante el pitch, esta es la secuencia completa (2 min).

## 1. Ollama (PowerShell en Windows)

```powershell
Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue
$env:OLLAMA_HOST="0.0.0.0:11434"    # OBLIGATORIO: sin esto WSL no lo alcanza
Start-Process -WindowStyle Hidden "C:\Users\braya\AppData\Local\Programs\Ollama\ollama.exe" -ArgumentList "serve"
```

Verificar: `curl http://localhost:11434/api/tags` responde con gemma4:e2b.

## 2. Backend (terminal WSL)

```bash
source ~/venv-hackathon/bin/activate
cd /mnt/c/Users/braya/Desktop/project_personal/hackathon/backend
OLLAMA_URL=http://172.26.176.1:11434 uvicorn main:app --host 0.0.0.0 --port 8000
```

Si la IP no funciona (cambia al reiniciar Windows), obtener la actual:
`ip route show default | awk '{print $3}'`

Verificar: `curl http://localhost:8000/api/salud` → `"ollama": true`.

Prueba completa (debe dar riesgo alto en ~2 s):

```bash
curl -s -X POST http://localhost:8000/api/analizar -H "Content-Type: application/json" \
  -d '{"texto": "URGENTE señoritas para night club en Cusco, pagamos pasaje, te quedas en el local, solo WhatsApp"}'
```

## 3. Frontend

Apuntar `VITE_API_URL` a `http://localhost:8000` y `npm run dev`.

## 4. URL publica temporal (opcional, para el adjunto de Kaggle)

```bash
cloudflared tunnel --url http://localhost:8000
```

Levantarla JUSTO antes de presentar: muere si se cierra la terminal.

## Guion de demo sugerido (90 segundos)

1. Pegar un aviso peligroso real (night club + pasaje pagado + WhatsApp)
   → RIESGO ALTO con banderas etiquetadas modelo/regla y la estadistica del
   departamento mencionado. ~2 segundos.
2. Pegar una oferta formal (RUC + planilla + portal institucional)
   → RIESGO BAJO. Demuestra que no es alarmista.
3. Subir una CAPTURA de pantalla de un aviso → Gemma 4 transcribe (vision
   nativa) y analiza. El punto fuerte multimodal.
4. Cerrar con el dato: "72.9% de las denuncias de trata empezaron asi. Todo
   esto corrio en esta laptop, sin internet: el aviso nunca salio de aqui."

## Numeros para el pitch

- 72.9% de denuncias de trata captadas por falsa oferta de trabajo (calculado
  del dataset PNP 2017-2023; Ministerio Publico corrobora 73.8%)
- 85% exactitud, 0 omisiones de riesgo alto sobre 20 casos nunca vistos
- 117 tok/s, ~2-6 s por analisis, en una GPU de laptop de 8 GB
- 86.2% de victimas son mujeres; 85.7% de ellas entre 12 y 29 años
