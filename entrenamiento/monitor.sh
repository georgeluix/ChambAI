#!/bin/bash
# Panel de progreso del entrenamiento.
#
#   bash monitor.sh          una foto del estado
#   watch -n 10 'bash monitor.sh'    actualizado cada 10 s
#
# El log usa retornos de carro para la barra de progreso, por eso se traduce
# con tr antes de leerlo. Python ademas bufferea la salida: los numeros se
# actualizan a saltos, no de forma continua.

cd "$(dirname "$0")"
LOG=train.log
[ -f "$LOG" ] || { echo "No hay train.log todavia"; exit 0; }

limpio() { tr '\r' '\n' < "$LOG"; }

echo "=============== ENTRENAMIENTO CHAMBA SEGURA ==============="
echo "  hora: $(date +%H:%M:%S)"

if pgrep -f "python entrenar.py --completo" > /dev/null; then
  echo "  estado: CORRIENDO   (transcurrido $(ps -o etime= -p $(pgrep -f 'python entrenar.py --completo' | head -1) | tr -d ' '))"
else
  echo "  estado: TERMINADO o DETENIDO"
fi

paso=$(limpio | grep -oE "[0-9]+/[0-9]+ \[[0-9:]+<[0-9:]+" | tail -1)
[ -n "$paso" ] && echo "  progreso: $paso  (transcurrido<restante)"

echo
echo "--- ultimas metricas ---"
limpio | grep -oE "'loss': '[0-9.e-]+'|'mean_token_accuracy': '[0-9.]+'|'epoch': '[0-9.]+'" \
  | paste - - - 2>/dev/null | tail -4

echo
echo "--- curva de perdida (1 de cada 20 registros) ---"
limpio | grep -oE "'loss': '[0-9.e-]+'" | sed -E "s/.*'([0-9.e-]+)'\$/\1/" \
  | awk 'NR%20==1' | tail -8 | tr '\n' ' '
echo

echo
echo "--- GPU ---"
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader

echo
echo "--- checkpoints ---"
ls -lt --time-style=+%H:%M ~/entrenamiento-out/checkpoints/ 2>/dev/null \
  | grep checkpoint | head -3 | awk '{print "  "$NF"   "$(NF-1)}'

if grep -q "Entrenamiento terminado" "$LOG" 2>/dev/null; then
  echo
  echo "=========== TERMINADO ==========="
  limpio | grep -A3 "Entrenamiento terminado"
fi
