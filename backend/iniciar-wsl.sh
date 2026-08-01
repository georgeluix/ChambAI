#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
ENTORNO="${CHAMBA_VENV:-$HOME/venv-hackathon}"
source "$ENTORNO/bin/activate"

export OLLAMA_URL="${OLLAMA_URL:-http://172.26.176.1:11434}"
export CHAMBA_MODO_ANALISIS="${CHAMBA_MODO_ANALISIS:-base}"
export CHAMBA_MODELO_BASE="${CHAMBA_MODELO_BASE:-gemma4:e2b}"
export CHAMBA_MODELO_ANALISIS="${CHAMBA_MODELO_ANALISIS:-$CHAMBA_MODELO_BASE}"

exec uvicorn main:app --host 0.0.0.0 --port 8000
