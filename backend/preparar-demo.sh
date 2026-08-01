#!/usr/bin/env bash
set -euo pipefail

MODELO_BASE="${CHAMBA_MODELO_BASE:-gemma4:e2b}"
MODELO_ANALISIS="${CHAMBA_MODELO_ANALISIS:-$MODELO_BASE}"
OLLAMA_URL="${OLLAMA_URL:-http://172.26.176.1:11434}"
USO_MIB=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)

if [ "$USO_MIB" -gt 2048 ]; then
  echo "GPU ocupada: ${USO_MIB} MiB. No se precalentara Ollama."
  echo "Confirma con el equipo que el entrenamiento termino."
  exit 1
fi

curl -fsS "$OLLAMA_URL/api/tags" >/dev/null || {
  echo "Ollama no responde. Inicialo con: ollama serve"
  exit 1
}

for MODELO in "$MODELO_BASE" "$MODELO_ANALISIS"; do
  curl -fsS "$OLLAMA_URL/api/chat" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODELO\",\"messages\":[{\"role\":\"user\",\"content\":\"Responde solo: listo\"}],\"stream\":false,\"think\":false,\"keep_alive\":\"10m\",\"options\":{\"num_ctx\":16384,\"temperature\":0}}" \
    >/dev/null
  echo "Modelo precalentado: $MODELO"
done

echo "Ollama listo para la demo."
