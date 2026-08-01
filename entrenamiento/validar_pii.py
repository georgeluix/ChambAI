# -*- coding: utf-8 -*-
"""Verifica que no quede informacion personal en los avisos recolectados.

Obligatorio antes de subir cualquier corpus con avisos reales al repositorio
publico. Reglas de la competencia, seccion 1.7:

  "Solutions must not include confidential, private, or personally identifiable
   information (PII) unless participants have explicit authorization and comply
   with all applicable laws and regulations."

Y Ley 29733 (Proteccion de Datos Personales, Peru), que es el mismo argumento
legal que sostiene el proyecto.

Uso:
  python validar_pii.py avisos-reales.jsonl
  python validar_pii.py avisos-reales.jsonl --corregir    # anonimiza y reescribe
"""
import json
import re
import shutil
import sys
from pathlib import Path

# --- patrones de PII -------------------------------------------------------
# Telefonos peruanos: moviles empiezan en 9 y tienen 9 digitos; fijos 7-8.
TELEFONO = re.compile(r"\b(?:\+?51[\s-]?)?9(?!X)\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b")
TELEFONO_FIJO = re.compile(r"\b(?:\(0?1\)|0?1[\s-])\s?\d{3}[\s.-]?\d{4}\b")
CORREO = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", re.I)
URL = re.compile(r"\b(?:https?://|www\.)\S+|\b(?:facebook|fb|instagram|tiktok)\.com/\S+", re.I)
DNI = re.compile(r"\bDNI[\s:N°º]*\d{8}\b", re.I)
RUC_TEXTO = re.compile(r"\bRUC[\s:N°º]*(\d{11})\b", re.I)

# marcadores ya anonimizados: no son hallazgos
ANONIMOS = re.compile(
    r"9XX[\s.]?XXX[\s.]?XXX|"
    r"[\w.+-]+@[\w.-]+\.invalid|"
    r"correo@ejemplo\.com|"
    r"20X{9}|"
    r"\bXXX+\b|<anonimizado>",
    re.I,
)

PATRONES = [
    ("telefono movil", TELEFONO),
    ("telefono fijo", TELEFONO_FIJO),
    ("correo", CORREO),
    ("url o perfil", URL),
    ("DNI", DNI),
]

REEMPLAZOS = [
    (TELEFONO, "9XX XXX XXX"),
    (TELEFONO_FIJO, "(01) XXX XXXX"),
    (CORREO, "correo@ejemplo.com"),
    (URL, "<enlace omitido>"),
    (DNI, "DNI XXXXXXXX"),
]


def limpiar_marcadores(texto):
    """Quita los marcadores ya anonimizados para no contarlos como hallazgos."""
    return ANONIMOS.sub(" ", texto)


def revisar(ruta):
    hallazgos, lineas, sin_fuente, sin_tipo = [], 0, [], []
    tipos, niveles = {}, {}

    for n, linea in enumerate(open(ruta, encoding="utf-8"), 1):
        linea = linea.strip()
        if not linea:
            continue
        lineas += 1
        try:
            ej = json.loads(linea)
        except json.JSONDecodeError as e:
            hallazgos.append((n, "JSON invalido", str(e)))
            continue

        if not ej.get("fuente"):
            sin_fuente.append(n)
        tipo = ej.get("tipo")
        if not tipo:
            sin_tipo.append(n)
        else:
            tipos[tipo] = tipos.get(tipo, 0) + 1

        try:
            usuario = ej["messages"][0]["content"]
            respuesta = ej["messages"][1]["content"]
        except (KeyError, IndexError, TypeError):
            hallazgos.append((n, "estructura invalida", linea[:80]))
            continue

        m = re.match(r"RIESGO: (\w+)", respuesta)
        if m:
            niveles[m.group(1)] = niveles.get(m.group(1), 0) + 1

        texto = limpiar_marcadores(usuario + "\n" + respuesta)
        for etiqueta, patron in PATRONES:
            for hit in patron.findall(texto):
                valor = hit if isinstance(hit, str) else hit[0]
                hallazgos.append((n, etiqueta, valor.strip()))

    return hallazgos, lineas, sin_fuente, sin_tipo, tipos, niveles


def corregir(ruta):
    salida = []
    nombre = Path(ruta).name
    metadatos_archivo = {
        "corpus-sintetico.jsonl": (
            "sintetico-propio",
            "sintetico",
            "Generador local reproducible generar_corpus.py",
        ),
        "avisos-externos.jsonl": (
            "sintetico-externo",
            "sintetico",
            "Ejemplos sinteticos redactados para diversidad",
        ),
        "evaluacion.jsonl": (
            "evaluacion-manual",
            "sintetico",
            "Casos de evaluacion redactados manualmente por el equipo",
        ),
    }.get(nombre)
    for linea in open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if not linea:
            continue
        ej = json.loads(linea)
        for msg in ej.get("messages", []):
            texto = msg.get("content", "")
            for patron, reemplazo in REEMPLAZOS:
                texto = patron.sub(reemplazo, texto)
            msg["content"] = texto
        if metadatos_archivo:
            ej["origen"] = ej.get("origen") or metadatos_archivo[0]
            ej["tipo"] = ej.get("tipo") or metadatos_archivo[1]
            ej["fuente"] = ej.get("fuente") or metadatos_archivo[2]
        origen = ej.get("origen", "")
        if not ej.get("tipo"):
            ej["tipo"] = "real anonimizado" if origen == "real-publicado" else "sintetico"
        if not ej.get("fuente"):
            fuentes = {
                "sintetico-propio": "Generador local reproducible generar_corpus.py",
                "sintetico-externo": "Ejemplos sinteticos redactados para diversidad",
                "evaluacion-manual": "Casos de evaluacion redactados manualmente por el equipo",
            }
            ej["fuente"] = fuentes.get(origen, "Origen documentado por el equipo SOINAR")
        salida.append(ej)
    original = Path(ruta)
    respaldo = original.with_name(original.name + ".antes-pii")
    if not respaldo.exists():
        shutil.copy2(original, respaldo)
    with open(ruta, "w", encoding="utf-8") as f:
        for ej in salida:
            f.write(json.dumps(ej, ensure_ascii=False) + "\n")
    print("Respaldo: %s" % respaldo)
    print("Anonimizado y reescrito: %s (%d ejemplos)" % (ruta, len(salida)))


def main():
    if len(sys.argv) < 2:
        print("Uso: python validar_pii.py <archivo.jsonl> [--corregir]")
        return 1
    ruta = sys.argv[1]

    if "--corregir" in sys.argv:
        corregir(ruta)

    hallazgos, lineas, sin_fuente, sin_tipo, tipos, niveles = revisar(ruta)

    print("Archivo: %s (%d ejemplos)" % (ruta, lineas))
    print("\n--- Trazabilidad (reglas 2.6 y codigo de conducta) ---")
    print("  con campo 'fuente' : %d/%d" % (lineas - len(sin_fuente), lineas))
    if sin_fuente:
        print("     FALTA en las lineas: %s" % sin_fuente[:20])
    print("  con campo 'tipo'   : %d/%d  %s" % (lineas - len(sin_tipo), lineas, tipos))
    if sin_tipo:
        print("     FALTA en las lineas: %s" % sin_tipo[:20])
    print("  distribucion       : %s" % niveles)

    print("\n--- PII (regla 1.7 y Ley 29733) ---")
    if not hallazgos:
        print("  OK  no se detecto informacion personal")
    else:
        porTipo = {}
        for n, etiqueta, valor in hallazgos:
            porTipo.setdefault(etiqueta, []).append((n, valor))
        for etiqueta, items in porTipo.items():
            print("  FALLA %s: %d ocurrencias" % (etiqueta, len(items)))
            for n, valor in items[:8]:
                print("        linea %d: %s" % (n, valor))
            if len(items) > 8:
                print("        ... y %d mas" % (len(items) - 8))
        print("\n  Corrige con: python validar_pii.py %s --corregir" % ruta)

    print("\n" + "=" * 60)
    if hallazgos or sin_fuente or sin_tipo:
        print("NO APTO para el repositorio publico")
        return 1
    print("APTO para el repositorio publico")
    return 0


if __name__ == "__main__":
    sys.exit(main())
