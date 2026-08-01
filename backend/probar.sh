#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
IMAGEN="${1:-aviso.jpg}"

# Aviso de riesgo alto por menores y cobro al postulante.
curl -sS -X POST "$BASE_URL/api/analizar" \
  -H "Content-Type: application/json" \
  -d '{"texto":"Buscamos chicas desde los 16 anos para bar nocturno. Deposita S/ 100 para el uniforme y escribe al WhatsApp 987654321."}'

# Aviso de riesgo bajo con empleador y condiciones verificables.
curl -sS -X POST "$BASE_URL/api/analizar" \
  -H "Content-Type: application/json" \
  -d '{"texto":"Empresa Ejemplo S.A.C. RUC 20123456789 busca auxiliar contable. Sueldo S/ 1800 en planilla. Postula en empleos.ejemplo.pe."}'

# Pasa la ruta de una captura como primer argumento: ./probar.sh captura.png
if [ -f "$IMAGEN" ]; then
  curl -sS -X POST "$BASE_URL/api/analizar-imagen" \
    -F "archivo=@${IMAGEN}"
else
  echo "Prueba de imagen omitida: no existe $IMAGEN" >&2
fi
