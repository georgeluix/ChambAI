# -*- coding: utf-8 -*-
"""Flujo de analisis de Chamba Segura implementado con LangGraph."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from contexto import contexto_local
from extractor import (
    BANDERA_SIN_ALERTAS,
    aplicar_reglas,
    calcular_puntaje,
    canonizar_bandera,
    gravedad_de_bandera,
    normalizar,
    parsear_salida_modelo,
)
from modelo import OllamaNoDisponible, analizar_aviso, transcribir_imagen


class EstadoAnalisis(TypedDict, total=False):
    texto: str
    origen: Literal["texto", "imagen"]
    imagen: bytes
    aviso_detectado: bool
    banderas_reglas: list[dict[str, str]]
    riesgo_forzado: str | None
    telefonos_enmascarados: list[str]
    salida_modelo: str
    analisis_modelo: dict[str, Any]
    contexto_estadistico: dict[str, Any]
    resultado: dict[str, Any]
    inicio: float


async def extraer(estado: EstadoAnalisis) -> dict[str, Any]:
    if estado["origen"] == "texto":
        return {"texto": estado["texto"], "aviso_detectado": True}

    transcripcion = await transcribir_imagen(estado["imagen"])
    detectado = transcripcion.strip().upper() != "SIN_AVISO"
    return {"texto": transcripcion, "aviso_detectado": detectado}


def reglas(estado: EstadoAnalisis) -> dict[str, Any]:
    if not estado.get("aviso_detectado", True):
        return {
            "banderas_reglas": [],
            "riesgo_forzado": None,
            "telefonos_enmascarados": [],
        }
    resultado = aplicar_reglas(estado["texto"])
    return {
        "banderas_reglas": resultado["banderas"],
        "riesgo_forzado": resultado["riesgo_forzado"],
        "telefonos_enmascarados": resultado["telefonos_enmascarados"],
    }


async def analizar(estado: EstadoAnalisis) -> dict[str, Any]:
    if not estado.get("aviso_detectado", True):
        return {
            "salida_modelo": "",
            "analisis_modelo": {"formato_valido": True},
        }

    salida = await analizar_aviso(estado["texto"], temperature=0)
    analisis = parsear_salida_modelo(salida)
    if not _analisis_semanticamente_valido(analisis):
        salida = await analizar_aviso(estado["texto"], temperature=0)
        analisis = parsear_salida_modelo(salida)
    if not _analisis_semanticamente_valido(analisis):
        analisis["formato_valido"] = False
    return {"salida_modelo": salida, "analisis_modelo": analisis}


def _analisis_semanticamente_valido(analisis: dict[str, Any]) -> bool:
    """Exige coherencia entre riesgo y un catalogo cerrado de banderas."""
    if not analisis.get("formato_valido"):
        return False
    banderas = analisis.get("banderas", [])
    sin_alertas = [
        bandera
        for bandera in banderas
        if normalizar(bandera) == normalizar(BANDERA_SIN_ALERTAS)
    ]
    if analisis.get("riesgo") == "bajo":
        return len(banderas) == 1 and len(sin_alertas) == 1
    if sin_alertas:
        return False
    return any(canonizar_bandera(bandera) for bandera in banderas)


def contextualizar(estado: EstadoAnalisis) -> dict[str, Any]:
    if not estado.get("aviso_detectado", True):
        contexto = contexto_local("")
    else:
        contexto = contexto_local(estado["texto"])
    return {"contexto_estadistico": contexto}


def _agregar_sin_duplicar(
    destino: list[dict[str, str]], bandera: dict[str, str]
) -> None:
    clave = normalizar(bandera["texto"])
    if any(normalizar(actual["texto"]) == clave for actual in destino):
        return
    destino.append(bandera)


def _riesgo_por_banderas(banderas: list[dict[str, str]]) -> str:
    graves = sum(bandera["gravedad"] == "grave" for bandera in banderas)
    criticas = sum(bandera["gravedad"] == "critica" for bandera in banderas)
    if graves or criticas >= 2:
        return "alto"
    if criticas or banderas:
        return "medio"
    return "bajo"


def _mayor_riesgo(*riesgos: str | None) -> str:
    orden = {"bajo": 0, "medio": 1, "alto": 2}
    validos = [riesgo for riesgo in riesgos if riesgo in orden]
    return max(validos, key=orden.get) if validos else "medio"


def _recomendacion(riesgo: str) -> str:
    if riesgo == "alto":
        return (
            "No respondas ni entregues datos personales. Reporta el aviso a la "
            "Linea 1818 del MININTER."
        )
    if riesgo == "medio":
        return (
            "Verifica el RUC, la direccion y las condiciones por escrito antes "
            "de compartir documentos o asistir a una entrevista."
        )
    return (
        "Verifica que el canal y los datos del empleador sean autenticos antes "
        "de postular."
    )


def consolidar(estado: EstadoAnalisis) -> dict[str, Any]:
    tiempo_ms = round((time.perf_counter() - estado["inicio"]) * 1000)
    if not estado.get("aviso_detectado", True):
        resultado = {
            "riesgo": "bajo",
            "puntaje": 0,
            "banderas": [],
            "explicacion": (
                "La imagen no contiene un aviso de trabajo reconocible. "
                "Prueba con una captura mas clara y completa."
            ),
            "recomendacion": "Envia una imagen donde el texto del aviso sea legible.",
            "contexto_local": estado["contexto_estadistico"],
            "texto_analizado": estado["texto"],
            "aviso_detectado": False,
            "formato_valido": True,
            "tiempo_ms": tiempo_ms,
        }
        return {"resultado": resultado}

    # Se vuelven a ejecutar las reglas para que el resultado final no pueda
    # depender de cambios accidentales en el estado intermedio del modelo.
    reglas_finales = aplicar_reglas(estado["texto"])
    banderas: list[dict[str, str]] = []
    for bandera in reglas_finales["banderas"]:
        _agregar_sin_duplicar(banderas, bandera)

    analisis = estado["analisis_modelo"]
    if analisis.get("formato_valido"):
        for texto_bandera in analisis.get("banderas", []):
            if normalizar(texto_bandera) == normalizar(BANDERA_SIN_ALERTAS):
                continue
            for texto_canonico in canonizar_bandera(texto_bandera):
                _agregar_sin_duplicar(
                    banderas,
                    {
                        "texto": texto_canonico,
                        "gravedad": gravedad_de_bandera(texto_canonico),
                        "origen": "modelo",
                    },
                )

    riesgo_banderas = _riesgo_por_banderas(banderas)
    riesgo_modelo = analisis.get("riesgo") if analisis.get("formato_valido") else None
    riesgo = _mayor_riesgo(
        riesgo_modelo, reglas_finales["riesgo_forzado"], riesgo_banderas
    )

    if analisis.get("formato_valido"):
        explicacion = analisis["explicacion"]
        if reglas_finales["riesgo_forzado"] == "alto" and analisis["riesgo"] != "alto":
            explicacion = (
                "Una regla determinista elevo el riesgo a alto. " + explicacion
            )
    else:
        explicacion = (
            "El modelo respondio, pero no respeto el formato esperado despues "
            "de dos intentos. Revisa manualmente el aviso y las banderas de reglas."
        )

    resultado = {
        "riesgo": riesgo,
        "puntaje": calcular_puntaje(banderas),
        "banderas": banderas,
        "explicacion": explicacion,
        "recomendacion": _recomendacion(riesgo),
        "contexto_local": estado["contexto_estadistico"],
        "texto_analizado": estado["texto"],
        "aviso_detectado": True,
        "formato_valido": bool(analisis.get("formato_valido")),
        "tiempo_ms": tiempo_ms,
    }
    if not analisis.get("formato_valido"):
        resultado["texto_crudo"] = estado["salida_modelo"]
    return {"resultado": resultado}


constructor = StateGraph(EstadoAnalisis)
constructor.add_node("extraer", extraer)
constructor.add_node("reglas", reglas)
constructor.add_node("analizar", analizar)
constructor.add_node("contextualizar", contextualizar)
constructor.add_node("consolidar", consolidar)
constructor.add_edge(START, "extraer")
constructor.add_edge("extraer", "reglas")
constructor.add_edge("reglas", "analizar")
constructor.add_edge("analizar", "contextualizar")
constructor.add_edge("contextualizar", "consolidar")
constructor.add_edge("consolidar", END)
GRAFO = constructor.compile()


async def ejecutar_texto(texto: str) -> dict[str, Any]:
    estado = await GRAFO.ainvoke(
        {"texto": texto, "origen": "texto", "inicio": time.perf_counter()}
    )
    return estado["resultado"]


async def ejecutar_imagen(imagen: bytes) -> dict[str, Any]:
    estado = await GRAFO.ainvoke(
        {"texto": "", "origen": "imagen", "imagen": imagen, "inicio": time.perf_counter()}
    )
    return estado["resultado"]


if __name__ == "__main__":
    ejemplo = "Buscamos chicas desde los 16 anos. Deposita S/ 50 para el uniforme."
    try:
        print(asyncio.run(ejecutar_texto(ejemplo)))
    except OllamaNoDisponible as error:
        print(f"No se pudo probar el grafo: {error}")
