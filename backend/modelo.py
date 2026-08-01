# -*- coding: utf-8 -*-
"""Cliente minimo para Gemma 4 servido localmente por Ollama."""

from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

import httpx

from extractor import (
    BANDERAS_CRITICAS,
    BANDERAS_GRAVES,
    BANDERAS_LEVES,
    es_aviso_laboral,
)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MODELO_BASE = os.getenv("CHAMBA_MODELO_BASE", "gemma4:e2b")
MODO_ANALISIS = os.getenv("CHAMBA_MODO_ANALISIS", "base").strip().lower()
if MODO_ANALISIS not in {"base", "lora"}:
    raise RuntimeError("CHAMBA_MODO_ANALISIS debe ser 'base' o 'lora'.")
MODELO_ANALISIS = os.getenv("CHAMBA_MODELO_ANALISIS", MODELO_BASE)
NUM_CTX = 16384
ADAPTADOR_ACTIVO = MODO_ANALISIS == "lora"
MAX_PREDICCION_ANALISIS = 320
MAX_PREDICCION_EXTRACCION = 1200
KEEP_ALIVE = os.getenv("CHAMBA_KEEP_ALIVE", "10m")

# Una sola inferencia a la vez evita que dos solicitudes intenten ocupar la
# misma VRAM durante la demo.
_TURNO_INFERENCIA = asyncio.Semaphore(1)

PROMPT_EXTRACCION = (
    "Realiza OCR de la imagen y transcribe TODO el texto visible. No decidas si "
    "es un aviso de trabajo: solo lee. Incluye letras pequenas del encabezado, "
    "centro y pie, aunque haya personas, logotipos, decoracion o poco contraste. "
    "Conserva palabras, numeros y saltos de linea. No interpretes, no resumas y "
    "no describas la imagen. Si existe cualquier texto legible, transcribelo. "
    "Responde solo SIN_TEXTO cuando no haya absolutamente ningun texto legible."
)

PROMPT_EXTRACCION_REINTENTO = (
    "Observa nuevamente la imagen con maxima atencion y actua solo como OCR. "
    "Ignora fotografias, fondos brillantes y adornos. Busca letras pequenas en "
    "la parte superior, central e inferior. Transcribe literalmente todas las "
    "palabras y numeros que puedas leer, sin decidir de que trata la imagen ni "
    "agregar comentarios. Solo si no hay ninguna letra legible responde SIN_TEXTO."
)


def _catalogo() -> str:
    secciones = (
        ("GRAVES (una sola basta para riesgo alto)", BANDERAS_GRAVES),
        ("CRITICAS (dos o mas hacen riesgo alto)", BANDERAS_CRITICAS),
        ("LEVES (empujan a riesgo medio)", BANDERAS_LEVES),
    )
    lineas: list[str] = []
    for titulo, banderas in secciones:
        lineas.append(f"{titulo}:")
        lineas.extend(f"- {bandera}" for bandera in banderas)
    return "\n".join(lineas)


PROMPT_ANALISIS = """Eres Chamba Segura, un analizador preventivo de avisos de trabajo en Peru.
Clasifica unicamente las senales presentes en el aviso. Usa las frases exactas del catalogo.
No inventes datos, empresas ni condiciones que no esten escritas.

CATALOGO DE BANDERAS
{catalogo}

Responde SIEMPRE con esta estructura exacta, sin markdown ni texto adicional:
RIESGO: bajo|medio|alto
BANDERAS:
- Una frase exacta del catalogo
EXPLICACION: Dos o tres oraciones claras.

Si el riesgo es bajo, la unica bandera debe ser:
- Ninguna señal de alerta detectada

EJEMPLO ALTO
AVISO: Se buscan senoritas de buena presencia para atender reservados de noche. Alojamiento en el mismo local. Solo WhatsApp.
RESPUESTA:
RIESGO: alto
BANDERAS:
- Filtro por sexo, edad y apariencia fisica sin relacion con la funcion
- Alojamiento dentro del centro de trabajo
- Servicios de acompañamiento en local privado y horario nocturno
- Contacto unicamente por mensajeria con un numero personal
EXPLICACION: El aviso combina filtros personales, trabajo nocturno privado y alojamiento en el local. Estas senales crean un riesgo alto de aislamiento y captacion.

EJEMPLO MEDIO
AVISO: Restaurante busca ayudante de cocina. El sueldo se conversa en entrevista. Turno de 6pm a 1am y postulacion por WhatsApp.
RESPUESTA:
RIESGO: medio
BANDERAS:
- Remuneracion no especificada en el aviso
- Trabajo en horario nocturno
- Postulacion por mensajeria personal
EXPLICACION: Faltan condiciones salariales y el unico canal indicado es mensajeria. Verifica la identidad del empleador y pide las condiciones por escrito.

EJEMPLO BAJO
AVISO: Empresa Ejemplo S.A.C. RUC 20123456789 busca auxiliar contable. Sueldo S/ 1800 en planilla. Postula en empleos.ejemplo.pe.
RESPUESTA:
RIESGO: bajo
BANDERAS:
- Ninguna señal de alerta detectada
EXPLICACION: El empleador, la remuneracion y el canal institucional son verificables. No se observan senales de alerta en el aviso.

AVISO A ANALIZAR:
{aviso}

RESPUESTA:
"""


class OllamaNoDisponible(RuntimeError):
    """Error controlado cuando el servicio local no puede completar la llamada."""


async def _generar(
    modelo: str,
    prompt: str,
    *,
    temperature: float = 0,
    imagen: bytes | None = None,
    num_predict: int,
) -> str:
    # /api/chat en lugar de /api/generate: Gemma 4 es un modelo con "thinking"
    # y en generate su salida cae en el campo thinking, dejando response vacio
    # (verificado: 41 s y texto vacio por generate; 1.7 s por chat sin thinking).
    # think=False desactiva el razonamiento oculto, que aqui solo quema tokens.
    mensaje: dict[str, Any] = {"role": "user", "content": prompt}
    if imagen is not None:
        mensaje["images"] = [base64.b64encode(imagen).decode("ascii")]
    cuerpo: dict[str, Any] = {
        "model": modelo,
        "messages": [mensaje],
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {
            "num_ctx": NUM_CTX,
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }

    timeout = httpx.Timeout(180.0, connect=5.0)
    try:
        async with _TURNO_INFERENCIA:
            async with httpx.AsyncClient(timeout=timeout) as cliente:
                respuesta = await cliente.post(f"{OLLAMA_URL}/api/chat", json=cuerpo)
                respuesta.raise_for_status()
    except httpx.ConnectError as error:
        raise OllamaNoDisponible(
            "Ollama no responde. Levantalo con 'ollama serve' y confirma que "
            f"el modelo {modelo} este instalado."
        ) from error
    except httpx.TimeoutException as error:
        raise OllamaNoDisponible(
            "Ollama excedio el tiempo de espera. Revisa la RAM disponible y "
            "vuelve a intentar cuando termine el entrenamiento."
        ) from error
    except httpx.RequestError as error:
        raise OllamaNoDisponible(
            "Se perdio la conexion con Ollama. Comprueba que 'ollama serve' "
            "siga activo y vuelve a intentar."
        ) from error
    except httpx.HTTPStatusError as error:
        detalle = error.response.text[:300]
        raise OllamaNoDisponible(
            f"Ollama rechazo la solicitud ({error.response.status_code}): {detalle}"
        ) from error

    try:
        contenido = respuesta.json().get("message", {}).get("content")
    except ValueError as error:
        raise OllamaNoDisponible("Ollama devolvio una respuesta que no es JSON valido.") from error
    if not isinstance(contenido, str):
        raise OllamaNoDisponible("Ollama respondio sin el campo de texto esperado.")
    return contenido.strip()


async def transcribir_imagen(imagen: bytes) -> str:
    primera = await _generar(
        MODELO_BASE,
        PROMPT_EXTRACCION,
        temperature=0,
        imagen=imagen,
        num_predict=MAX_PREDICCION_EXTRACCION,
    )
    if es_aviso_laboral(primera):
        return primera

    # Una segunda mirada recupera afiches con tipografia pequena o fondos
    # decorativos. Solo ocurre cuando la primera transcripcion no contiene
    # suficientes señales laborales.
    segunda = await _generar(
        MODELO_BASE,
        PROMPT_EXTRACCION_REINTENTO,
        temperature=0,
        imagen=imagen,
        num_predict=MAX_PREDICCION_EXTRACCION,
    )
    if segunda.strip().upper() not in {"SIN_TEXTO", "SIN_AVISO"}:
        return segunda
    return primera


async def analizar_aviso(texto: str, temperature: float = 0) -> str:
    if ADAPTADOR_ACTIVO:
        # Es exactamente el prompt usado al entrenar y verificar el LoRA.
        prompt = f"Analiza este aviso de empleo:\n\n{texto}"
    else:
        prompt = PROMPT_ANALISIS.format(catalogo=_catalogo(), aviso=texto)
    return await _generar(
        MODELO_ANALISIS,
        prompt,
        temperature=temperature,
        num_predict=MAX_PREDICCION_ANALISIS,
    )


async def estado_ollama() -> dict[str, Any]:
    """Comprueba el servidor, los modelos requeridos y la capacidad de vision."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as cliente:
            respuesta = await cliente.get(f"{OLLAMA_URL}/api/tags")
            respuesta.raise_for_status()
            modelos = respuesta.json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return {
            "ok": False,
            "modelo": MODELO_ANALISIS,
            "ollama": False,
            "adaptador": ADAPTADOR_ACTIVO,
        }

    nombres = {
        modelo.get("name") or modelo.get("model")
        for modelo in modelos
        if isinstance(modelo, dict)
    }
    requeridos = {MODELO_BASE, MODELO_ANALISIS}
    disponibles = requeridos.issubset(nombres)
    vision = False
    if disponibles:
        try:
            async with httpx.AsyncClient(timeout=5.0) as cliente:
                detalle = await cliente.post(
                    f"{OLLAMA_URL}/api/show", json={"model": MODELO_BASE}
                )
                detalle.raise_for_status()
                vision = "vision" in detalle.json().get("capabilities", [])
        except (httpx.HTTPError, ValueError):
            vision = False
    return {
        "ok": disponibles and vision,
        "modelo": MODELO_ANALISIS,
        "ollama": True,
        "adaptador": ADAPTADOR_ACTIVO,
    }


if __name__ == "__main__":
    estado = asyncio.run(estado_ollama())
    print(estado)
    if not estado["ollama"]:
        print("Inicia Ollama con: ollama serve")
    elif not estado["ok"]:
        print(f"Verifica los modelos base={MODELO_BASE} y analisis={MODELO_ANALISIS}")
