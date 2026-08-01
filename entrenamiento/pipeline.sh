#!/bin/bash
# Orquestador del entrenamiento de Chamba Segura.
# Se detiene en la primera compuerta que falla. Cada fase con timestamp.
#
# Uso: bash pipeline.sh

set -u
cd "$(dirname "$0")"
source ~/venv-hackathon/bin/activate

export MAX_LEN="${MAX_LEN:-512}"
export MODELO_BASE="${MODELO_BASE:-/home/abel_brayan/gemma-4-e2b}"

fase() { echo; echo "############ $1 :: $(date +%H:%M:%S) ############"; }
fin()  { echo "############ fin $1 :: $(date +%H:%M:%S) ############"; }

abortar() {
  echo
  echo "########################################################"
  echo "  DETENIDO EN: $1"
  echo "  Hora: $(date +%H:%M:%S)"
  echo "########################################################"
  exit 1
}

# --- datos -----------------------------------------------------------------
if [ ! -f corpus.jsonl ] || [ ! -f evaluacion.jsonl ]; then
  fase "GENERACION DE DATOS"
  python generar_corpus.py     || abortar "generar_corpus.py"
  python generar_evaluacion.py || abortar "generar_evaluacion.py"
  fin "GENERACION DE DATOS"
fi

# --- Compuerta 1 -----------------------------------------------------------
fase "COMPUERTA 1 - validacion del corpus"
python validar_corpus.py || abortar "COMPUERTA 1 (datos). Corrige corpus.jsonl y vuelve a correr."
fin "COMPUERTA 1"

# --- Compuerta 2 -----------------------------------------------------------
fase "COMPUERTA 2 - chat template"
python inspeccionar_template.py || abortar "COMPUERTA 2 (template). Revisa chat_template.jinja del modelo."
fin "COMPUERTA 2"

# --- Compuerta 3 -----------------------------------------------------------
fase "COMPUERTA 3 - canario (20 steps, ~2 min)"
python entrenar.py --canario
codigo=$?
fin "COMPUERTA 3"
if [ $codigo -eq 1 ]; then
  abortar "COMPUERTA 3 (gradientes muertos o muy pocos steps)."
elif [ $codigo -eq 2 ]; then
  echo
  echo "El canario quedo PARCIAL: gradientes vivos pero la perdida no baja."
  echo "Reintento sugerido: LR=1e-4 python entrenar.py --canario"
  read -p "Lanzar el completo igual? (s/N) " respuesta
  [ "$respuesta" = "s" ] || abortar "COMPUERTA 3 (parcial, cancelado por el operador)."
fi

# --- confirmacion humana ---------------------------------------------------
echo
echo "El canario paso. El entrenamiento completo toma ~10-15 min."
echo "IMPORTANTE: nadie debe levantar Ollama mientras corre (los 8 GB son compartidos)."
read -p "Lanzar el entrenamiento completo? (s/N) " respuesta
[ "$respuesta" = "s" ] || abortar "lanzamiento cancelado por el operador."

# --- entrenamiento completo ------------------------------------------------
fase "ENTRENAMIENTO COMPLETO (nohup)"
nohup python entrenar.py --completo > train.log 2>&1 &
pid=$!
echo "Lanzado con PID $pid, log en train.log"
echo
echo "Para monitorear:   tail -f train.log"
echo "Para ver la VRAM:  watch -n 5 nvidia-smi"
echo
echo "Al terminar:       python verificar_adaptador.py   (COMPUERTA 4)"
echo "Grafica de perdida: perdidas.png"
