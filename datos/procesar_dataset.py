# -*- coding: utf-8 -*-
"""Convierte el Excel de denuncias de trata (PNP/MININTER) en un JSON compacto.

Fuente: 6522273-base-de-datos-trata-de-personas-2024.xlsx
Datos Abiertos del Estado Peruano - denuncias registradas por la PNP 2017-2023.
180 600 filas de conteos agregados por departamento/provincia/distrito/comisaria.

Se corre UNA vez en CPU (~3 s); el backend solo lee datos_trata.json, sin pandas
y sin internet.

OJO: cada categoria trae filas *_TOTAL y *_SUB TOTAL que replican la suma de sus
propias subcategorias. Si no se excluyen, todo porcentaje sale exactamente a la
mitad del real.

Uso: python procesar_dataset.py
"""
import json
import os
import re

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(AQUI, "..", "documentacion", "datasets",
                    "6522273-base-de-datos-trata-de-personas-2024.xlsx")
SALIDA = os.path.join(AQUI, "datos_trata.json")

# categoria del dataset -> (clave de salida, prefijo a recortar)
CATEGORIAS = {
    "CAPTACIÓN": ("captacion", "C_"),
    "MEDIO EMPLEADO POR EL TRATANTE": ("medio", "M_"),
    "FINALIDAD DEL TIPO DE DELITO": ("finalidad", "F1_"),
    "EXPLOTACIÓN": ("lugar_explotacion", "F2_"),
    "INSTRUCCIÓN DE LA VÍCTIMA": ("instruccion", "P3_"),
    "TIPO RECLUTAMIENTO": ("reclutamiento", "T_"),
    "VÍNCULO CON EL TRATANTE": ("vinculo", "P4_"),
    "FEMENINO GRUPO EDAD": ("edad_mujeres", "EF_"),
    "MASCULINO GRUPO DE EDAD": ("edad_hombres", "EM_"),
}


def limpiar(texto, prefijo):
    t = str(texto).replace(prefijo, "").replace("(ESPECIFICAR)", "").strip()
    return re.sub(r"\s+", " ", t).lower()


def distribucion(sub, prefijo):
    total = sub.sum()
    if not total:
        return {}, 0
    return ({limpiar(k, prefijo): {"n": int(v), "pct": round(100.0 * v / total, 1)}
             for k, v in sub.sort_values(ascending=False).items() if v > 0},
            int(total))


def main():
    df = pd.read_excel(XLSX)
    df.columns = ["anio", "mes", "ccdd", "depto", "provincia", "distrito",
                  "comisaria", "categoria", "subcategoria", "valor"]
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    for c in ("depto", "provincia", "distrito"):
        df[c] = df[c].astype(str).str.strip().str.upper().replace("NAN", None)

    # las filas TOTAL / SUB TOTAL duplican el conteo
    d = df[~df.subcategoria.astype(str).str.contains("TOTAL", na=False)]

    salida = {
        "fuente": "PNP - MININTER, Datos Abiertos del Estado Peruano",
        "dataset": "Denuncias por trata de personas 2017-2023",
        "periodo": "2017-2023",
        "nacional": {},
        "departamentos": {},
    }

    for cat, (clave, pref) in CATEGORIAS.items():
        sub = d[d.categoria == cat].groupby("subcategoria").valor.sum()
        dist, total = distribucion(sub, pref)
        salida["nacional"][clave] = {"total": total, "distribucion": dist}

    cap = d[d.categoria == "CAPTACIÓN"]
    salida["nacional"]["denuncias_total"] = int(cap.valor.sum())
    salida["nacional"]["por_anio"] = {
        str(a): int(v) for a, v in
        d[d.subcategoria == "C_OFERTA DE TRABAJO"].groupby("anio").valor.sum().items()}

    muj = d[d.categoria == "FEMENINO GRUPO EDAD"].valor.sum()
    hom = d[d.categoria == "MASCULINO GRUPO DE EDAD"].valor.sum()
    salida["nacional"]["victimas"] = {
        "mujeres_pct": round(100.0 * muj / (muj + hom), 1),
        "hombres_pct": round(100.0 * hom / (muj + hom), 1),
    }

    tot_dep = cap.groupby("depto").valor.sum()
    ot_dep = cap[cap.subcategoria == "C_OFERTA DE TRABAJO"].groupby("depto").valor.sum()
    ranking = tot_dep.sort_values(ascending=False)
    for i, (dep, total) in enumerate(ranking.items(), 1):
        if not dep or not total:
            continue
        ot = float(ot_dep.get(dep, 0))
        provs = (cap[cap.depto == dep].groupby("provincia").valor.sum()
                 .sort_values(ascending=False))
        salida["departamentos"][dep] = {
            "denuncias": int(total),
            "por_oferta_de_trabajo": int(ot),
            "pct_oferta_de_trabajo": round(100.0 * ot / total, 1),
            "ranking_nacional": i,
            "pct_del_total_nacional": round(100.0 * total / ranking.sum(), 1),
            "provincias": {p: int(v) for p, v in provs.items() if p and v > 0},
        }

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)

    n = salida["nacional"]
    print("datos_trata.json generado (%.0f KB)" % (os.path.getsize(SALIDA) / 1024))
    print("  denuncias 2017-2023      : %d" % n["denuncias_total"])
    print("  captadas por oferta labo.: %.1f%%" % n["captacion"]["distribucion"]["oferta de trabajo"]["pct"])
    print("  victimas mujeres         : %.1f%%" % n["victimas"]["mujeres_pct"])
    print("  departamentos            : %d" % len(salida["departamentos"]))


if __name__ == "__main__":
    main()
