# -*- coding: utf-8 -*-
"""Contexto estadistico real de trata de personas en Peru.

Lee datos_trata.json (generado una vez por procesar_dataset.py desde el Excel
de Datos Abiertos del Estado). Sin pandas, sin internet, sin GPU: es un dict.

Reparto de trabajo del sistema:
  - Gemma 4 lee el aviso y razona sobre el texto.
  - Este modulo aporta el dato local verificable que el modelo no sabe y no
    debe inventar (cuantas denuncias hay en ese departamento, que porcentaje
    entro por oferta de trabajo).

Uso:
    from datos_trata import contexto_para_aviso, ficha_nacional
    ctx = contexto_para_aviso("Trabajo en Puerto Maldonado, viaje pagado")
"""
import json
import os
import re
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(AQUI, "datos_trata.json"), encoding="utf-8") as _f:
    DATOS = json.load(_f)

NACIONAL = DATOS["nacional"]
DEPARTAMENTOS = DATOS["departamentos"]

# Ciudades y zonas que aparecen en los avisos -> departamento del dataset.
# Incluye los destinos de traslado mas citados en denuncias de captacion laboral.
CIUDADES = {
    "lima": "LIMA", "callao": "CALLAO", "comas": "LIMA", "los olivos": "LIMA",
    "san juan de lurigancho": "LIMA", "ate": "LIMA", "villa el salvador": "LIMA",
    "miraflores": "LIMA", "surco": "LIMA", "canete": "LIMA", "huacho": "LIMA",
    "arequipa": "AREQUIPA", "trujillo": "LA LIBERTAD", "chiclayo": "LAMBAYEQUE",
    "piura": "PIURA", "sullana": "PIURA", "cusco": "CUSCO", "cuzco": "CUSCO",
    "quillabamba": "CUSCO", "iquitos": "LORETO", "maynas": "LORETO",
    "nauta": "LORETO", "huancayo": "JUNIN", "la oroya": "JUNIN",
    "satipo": "JUNIN", "tacna": "TACNA", "chimbote": "ANCASH",
    "huaraz": "ANCASH", "ica": "ICA", "chincha": "ICA", "nazca": "ICA",
    "pisco": "ICA", "ayacucho": "AYACUCHO", "huamanga": "AYACUCHO",
    "cajamarca": "CAJAMARCA", "jaen": "CAJAMARCA", "tarapoto": "SAN MARTIN",
    "moyobamba": "SAN MARTIN", "juanjui": "SAN MARTIN",
    "puerto maldonado": "MADRE DE DIOS", "tambopata": "MADRE DE DIOS",
    "la pampa": "MADRE DE DIOS", "delta uno": "MADRE DE DIOS",
    "huepetuhe": "MADRE DE DIOS", "madre de dios": "MADRE DE DIOS",
    "pucallpa": "UCAYALI", "atalaya": "UCAYALI", "puno": "PUNO",
    "juliaca": "PUNO", "desaguadero": "PUNO", "ilave": "PUNO",
    "huanuco": "HUANUCO", "tingo maria": "HUANUCO", "cerro de pasco": "PASCO",
    "tumbes": "TUMBES", "zarumilla": "TUMBES", "moquegua": "MOQUEGUA",
    "ilo": "MOQUEGUA", "abancay": "APURIMAC", "andahuaylas": "APURIMAC",
    "huancavelica": "HUANCAVELICA", "chachapoyas": "AMAZONAS",
    "bagua": "AMAZONAS",
}


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFKD", t.lower())
                   if not unicodedata.combining(c))


# indice normalizado de los departamentos del dataset
_INDICE = {_sin_tildes(d): d for d in DEPARTAMENTOS}


def _resolver(nombre):
    """Devuelve la clave real del dataset para un nombre de departamento."""
    return _INDICE.get(_sin_tildes(nombre or ""))


def detectar_lugares(texto):
    """Departamentos mencionados en el texto, del mas especifico al menos."""
    t = _sin_tildes(texto)
    hallados = []
    # las ciudades primero: son mas informativas que el nombre del departamento
    for ciudad, depto in sorted(CIUDADES.items(), key=lambda x: -len(x[0])):
        if re.search(r"\b%s\b" % re.escape(ciudad), t):
            clave = _resolver(depto)
            if clave and clave not in hallados:
                hallados.append(clave)
    for norm, real in _INDICE.items():
        if re.search(r"\b%s\b" % re.escape(norm), t) and real not in hallados:
            hallados.append(real)
    return hallados


def contexto_departamento(nombre):
    """Ficha de un departamento, o None si no existe en el dataset."""
    clave = _resolver(nombre)
    if not clave:
        return None
    d = dict(DEPARTAMENTOS[clave])
    d["departamento"] = clave
    return d


def frase_departamento(nombre):
    """Una linea citable para la respuesta al usuario."""
    d = contexto_departamento(nombre)
    if not d:
        return None
    bonito = " ".join(p if p in ("de", "y") else p.capitalize()
                      for p in d["departamento"].lower().split())
    return ("%s registra %d denuncias de trata (2017-2023), el puesto %d del pais; "
            "%.1f%% de esos casos empezaron con una oferta de trabajo."
            % (bonito, d["denuncias"], d["ranking_nacional"], d["pct_oferta_de_trabajo"]))


def contexto_para_aviso(texto):
    """Contexto listo para inyectar en el prompt o mostrar en la interfaz.

    Devuelve dict con las estadisticas nacionales y las de los departamentos
    que el aviso menciona. Si no menciona ninguno, solo el contexto nacional.
    """
    lugares = detectar_lugares(texto)
    return {
        "nacional": ficha_nacional(),
        "lugares_mencionados": lugares,
        "detalle_lugares": [contexto_departamento(l) for l in lugares],
        "frases": [f for f in (frase_departamento(l) for l in lugares) if f],
    }


def ficha_nacional():
    """Las cifras que sostienen el producto."""
    cap = NACIONAL["captacion"]["distribucion"]
    med = NACIONAL["medio"]["distribucion"]
    fin = NACIONAL["finalidad"]["distribucion"]
    ins = NACIONAL["instruccion"]["distribucion"]
    return {
        "denuncias_2017_2023": NACIONAL["denuncias_total"],
        "pct_captadas_por_oferta_de_trabajo": cap["oferta de trabajo"]["pct"],
        "pct_medio_engano": med.get("engaño", {}).get("pct"),
        "pct_finalidad_explotacion_sexual": fin.get("explotacion sexual", {}).get("pct"),
        "pct_finalidad_explotacion_laboral": fin.get("explotacion laboral", {}).get("pct"),
        "pct_victimas_mujeres": NACIONAL["victimas"]["mujeres_pct"],
        "pct_victimas_solo_secundaria": ins.get("secundaria", {}).get("pct"),
        "pct_reclutamiento_nacional": NACIONAL["reclutamiento"]["distribucion"].get("nacional", {}).get("pct"),
        "fuente": DATOS["fuente"],
    }


def top_departamentos(n=10):
    return sorted(
        ({"departamento": k, **v} for k, v in DEPARTAMENTOS.items()),
        key=lambda d: -d["denuncias"])[:n]


def serie_anual():
    """Denuncias captadas por oferta de trabajo, por año (para el frontend)."""
    return NACIONAL["por_anio"]


if __name__ == "__main__":
    print("=== Ficha nacional ===")
    for k, v in ficha_nacional().items():
        print("  %-38s %s" % (k, v))
    print("\n=== Top 5 departamentos ===")
    for d in top_departamentos(5):
        print("  %-16s %5d denuncias  %4.1f%% por oferta de trabajo"
              % (d["departamento"], d["denuncias"], d["pct_oferta_de_trabajo"]))
    print("\n=== Prueba sobre un aviso ===")
    aviso = ("Se busca personal para campamento en Puerto Maldonado, "
             "viaje pagado desde Juliaca, alojamiento incluido.")
    print("  aviso:", aviso)
    ctx = contexto_para_aviso(aviso)
    print("  lugares:", ctx["lugares_mencionados"])
    for f in ctx["frases"]:
        print("   -", f)
