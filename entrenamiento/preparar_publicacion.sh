#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

ACTIVOS="$(pgrep -af 'entrenar.py|verificar_adaptador.py|evaluar.py' || true)"
if [ -n "$ACTIVOS" ]; then
  echo "Hay un proceso de entrenamiento o evaluacion activo. No se modificaran los datos:"
  echo "$ACTIVOS"
  exit 1
fi

echo "[1/5] Anonimizando y completando trazabilidad"
for ARCHIVO in corpus-sintetico.jsonl avisos-reales.jsonl avisos-externos.jsonl; do
  python validar_pii.py "$ARCHIVO" --corregir
done

echo "[2/5] Normalizando las fuentes al catalogo cerrado"
python normalizar_catalogo.py \
  corpus-sintetico.jsonl avisos-reales.jsonl avisos-externos.jsonl --aplicar

echo "[3/5] Reconstruyendo corpus y evaluacion"
python mezclar_corpus.py
python generar_evaluacion.py

echo "[4/5] Verificando privacidad de todos los archivos publicables"
for ARCHIVO in corpus-sintetico.jsonl avisos-reales-crudo.jsonl avisos-reales.jsonl \
               avisos-externos.jsonl corpus.jsonl evaluacion.jsonl; do
  python validar_pii.py "$ARCHIVO"
done

echo "[5/5] Ejecutando la compuerta del corpus"
python validar_corpus.py

echo "Datos listos para publicacion. Los respaldos .antes-* son privados y estan ignorados."
