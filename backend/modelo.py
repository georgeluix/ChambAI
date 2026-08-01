# -*- coding: utf-8 -*-
"""Cliente de Gemma para Ollama local o la Gemini API hospedada."""

from __future__ import annotations

import asyncio
import base64
import os
import re
from typing import Any

import httpx

from extractor import (
    BANDERAS_CRITICAS,
    BANDERAS_GRAVES,
    BANDERAS_LEVES,
    es_aviso_laboral,
)


PROVEEDOR = os.getenv("CHAMBA_PROVEEDOR", "ollama").strip().lower()
if PROVEEDOR not in {"ollama", "gemini_api"}:
    raise RuntimeError("CHAMBA_PROVEEDOR debe ser 'ollama' o 'gemini_api'.")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
GEMINI_API_URL = os.getenv(
    "GEMINI_API_URL", "https://generativelanguage.googleapis.com"
).rstrip("/")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODELO_GEMINI_API = os.getenv("GEMMA_API_MODEL", "gemma-4-26b-a4b-it")
MODELO_BASE = os.getenv("CHAMBA_MODELO_BASE", "gemma4:e2b")
MODELO_VISION = os.getenv(
    "CHAMBA_MODELO_VISION",
    MODELO_GEMINI_API if PROVEEDOR == "gemini_api" else "gemma3:4b",
)
MODO_ANALISIS = os.getenv("CHAMBA_MODO_ANALISIS", "base").strip().lower()
if MODO_ANALISIS not in {"base", "lora"}:
    raise RuntimeError("CHAMBA_MODO_ANALISIS debe ser 'base' o 'lora'.")
MODELO_ANALISIS = os.getenv(
    "CHAMBA_MODELO_ANALISIS",
    MODELO_GEMINI_API if PROVEEDOR == "gemini_api" else MODELO_BASE,
)
NUM_CTX = 16384
ADAPTADOR_ACTIVO = MODO_ANALISIS == "lora"
if PROVEEDOR == "gemini_api" and ADAPTADOR_ACTIVO:
    raise RuntimeError("La Gemini API hospedada no puede cargar el LoRA local.")
MAX_PREDICCION_ANALISIS = 320
MAX_PREDICCION_EXTRACCION = 1200
KEEP_ALIVE = os.getenv("CHAMBA_KEEP_ALIVE", "10m")

# Una sola inferencia a la vez evita que dos solicitudes intenten ocupar la
# misma VRAM durante la demo.
_TURNO_INFERENCIA = asyncio.Semaphore(1)

PROMPT_EXTRACCION = (
    "Observa la imagen completa y responde sin markdown con dos bloques. En "
    "TEXTO_VISIBLE transcribe literalmente TODO el texto: encabezado, centro, "
    "pie, palabras y numeros. En CONTEXTO_VISUAL describe brevemente solo los "
    "elementos visibles relevantes para entender el aviso, como tipo de local, "
    "personas, vestimenta, bebidas o ambiente. No identifiques personas, no "
    "supongas edades, delitos ni nivel de riesgo. Usa exactamente este formato:\n"
    "TEXTO_VISIBLE:\n<transcripcion o SIN_TEXTO>\n"
    "CONTEXTO_VISUAL:\n<descripcion objetiva o SIN_CONTEXTO>"
)

PROMPT_EXTRACCION_REINTENTO = (
    "Revisa nuevamente toda la imagen, incluida la tipografia pequena sobre "
    "fondos brillantes. Responde sin markdown con TEXTO_VISIBLE y "
    "CONTEXTO_VISUAL. Transcribe literalmente las palabras y numeros; despues "
    "describe de forma objetiva el lugar, personas, vestimenta, bebidas y "
    "ambiente visibles. No supongas edades, delitos ni nivel de riesgo. Formato:\n"
    "TEXTO_VISIBLE:\n<transcripcion o SIN_TEXTO>\n"
    "CONTEXTO_VISUAL:\n<descripcion objetiva o SIN_CONTEXTO>"
)

_MARCA_CONTEXTO_VISUAL = re.compile(
    r"(?im)^\s*(?:\*\*)?CONTEXTO_VISUAL(?:\*\*)?\s*:\s*"
)
_ENCABEZADO_TEXTO = re.compile(
    r"(?is)^\s*(?:\*\*)?TEXTO(?:_VISIBLE)?(?:\*\*)?\s*:\s*"
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
    """Error controlado cuando el proveedor no puede completar la llamada."""


def _mime_imagen(imagen: bytes) -> str:
    if imagen.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if imagen.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(imagen) >= 12 and imagen.startswith(b"RIFF") and imagen[8:12] == b"WEBP":
        return "image/webp"
    raise OllamaNoDisponible("La imagen no tiene un formato compatible con Gemma.")


async def _generar_gemini_api(
    modelo: str,
    prompt: str,
    *,
    temperature: float,
    imagen: bytes | None,
    num_predict: int,
) -> str:
    if not GEMINI_API_KEY:
        raise OllamaNoDisponible(
            "Falta GEMINI_API_KEY en el backend. Configurala mediante Secret Manager."
        )

    partes: list[dict[str, Any]] = [{"text": prompt}]
    if imagen is not None:
        partes.insert(
            0,
            {
                "inlineData": {
                    "mimeType": _mime_imagen(imagen),
                    "data": base64.b64encode(imagen).decode("ascii"),
                }
            },
        )
    cuerpo = {
        "contents": [{"role": "user", "parts": partes}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": num_predict,
            "thinkingConfig": {"thinkingLevel": "minimal"},
        },
    }
    url = f"{GEMINI_API_URL}/v1beta/models/{modelo}:generateContent"
    timeout = httpx.Timeout(180.0, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as cliente:
            respuesta = await cliente.post(
                url,
                headers={"X-Goog-Api-Key": GEMINI_API_KEY},
                json=cuerpo,
            )
            respuesta.raise_for_status()
    except httpx.TimeoutException as error:
        raise OllamaNoDisponible(
            "Gemma hospedado excedio el tiempo de espera. Intenta nuevamente."
        ) from error
    except httpx.RequestError as error:
        raise OllamaNoDisponible(
            "No se pudo conectar con la Gemini API hospedada."
        ) from error
    except httpx.HTTPStatusError as error:
        detalle = error.response.text[:300]
        raise OllamaNoDisponible(
            f"La Gemini API rechazo la solicitud ({error.response.status_code}): {detalle}"
        ) from error

    try:
        datos = respuesta.json()
        partes_salida = datos["candidates"][0]["content"]["parts"]
        textos = [
            parte["text"]
            for parte in partes_salida
            if isinstance(parte, dict)
            and isinstance(parte.get("text"), str)
            and not parte.get("thought", False)
        ]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise OllamaNoDisponible(
            "La Gemini API respondio sin el contenido de texto esperado."
        ) from error
    contenido = "\n".join(textos).strip()
    if not contenido:
        raise OllamaNoDisponible("Gemma hospedado devolvio una respuesta vacia.")
    return contenido


async def _generar(
    modelo: str,
    prompt: str,
    *,
    temperature: float = 0,
    imagen: bytes | None = None,
    num_predict: int,
) -> str:
    async with _TURNO_INFERENCIA:
        if PROVEEDOR == "gemini_api":
            return await _generar_gemini_api(
                modelo,
                prompt,
                temperature=temperature,
                imagen=imagen,
                num_predict=num_predict,
            )
        return await _generar_ollama(
            modelo,
            prompt,
            temperature=temperature,
            imagen=imagen,
            num_predict=num_predict,
        )


async def _generar_ollama(
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


def _parsear_extraccion_visual(salida: str) -> dict[str, str]:
    """Separa OCR y contexto aunque Gemma agregue negritas accidentales."""
    partes = _MARCA_CONTEXTO_VISUAL.split(salida.strip(), maxsplit=1)
    texto = _ENCABEZADO_TEXTO.sub("", partes[0]).strip(" \r\n*")
    contexto = partes[1].strip(" \r\n*") if len(partes) == 2 else ""
    if not texto:
        texto = "SIN_TEXTO"
    if contexto.upper() == "SIN_CONTEXTO":
        contexto = ""
    return {"texto": texto, "contexto_visual": contexto}


def _parece_aviso(extraccion: dict[str, str]) -> bool:
    return es_aviso_laboral(extraccion["texto"]) or es_aviso_laboral(
        extraccion["contexto_visual"]
    )


async def extraer_imagen(imagen: bytes) -> dict[str, str]:
    primera = await _generar(
        MODELO_VISION,
        PROMPT_EXTRACCION,
        temperature=0,
        imagen=imagen,
        num_predict=MAX_PREDICCION_EXTRACCION,
    )
    extraccion_primera = _parsear_extraccion_visual(primera)
    if _parece_aviso(extraccion_primera):
        return extraccion_primera

    # Una segunda mirada recupera afiches con tipografia pequena o fondos
    # decorativos. Solo ocurre cuando la primera transcripcion no contiene
    # suficientes señales laborales.
    segunda = await _generar(
        MODELO_VISION,
        PROMPT_EXTRACCION_REINTENTO,
        temperature=0,
        imagen=imagen,
        num_predict=MAX_PREDICCION_EXTRACCION,
    )
    extraccion_segunda = _parsear_extraccion_visual(segunda)
    if _parece_aviso(extraccion_segunda):
        return extraccion_segunda
    if len(extraccion_segunda["texto"]) > len(extraccion_primera["texto"]):
        return extraccion_segunda
    return extraccion_primera


async def transcribir_imagen(imagen: bytes) -> str:
    """Compatibilidad para consumidores que solo necesitan el texto OCR."""
    return (await extraer_imagen(imagen))["texto"]


async def analizar_aviso(
    texto: str, temperature: float = 0, contexto_visual: str = ""
) -> str:
    entrada = texto
    if contexto_visual:
        entrada = (
            f"{texto}\n\nCONTEXTO VISUAL OBSERVABLE (no es una conclusion de "
            f"riesgo):\n{contexto_visual}"
        )
    if ADAPTADOR_ACTIVO:
        # Es exactamente el prompt usado al entrenar y verificar el LoRA.
        prompt = f"Analiza este aviso de empleo:\n\n{entrada}"
    else:
        prompt = PROMPT_ANALISIS.format(catalogo=_catalogo(), aviso=entrada)
    return await _generar(
        MODELO_ANALISIS,
        prompt,
        temperature=temperature,
        num_predict=MAX_PREDICCION_ANALISIS,
    )


async def _estado_gemini_api() -> dict[str, Any]:
    estado = {
        "ok": False,
        "modelo": MODELO_ANALISIS,
        "modelo_vision": MODELO_VISION,
        "proveedor": "gemini_api",
        "ollama": False,
        "adaptador": False,
    }
    if not GEMINI_API_KEY:
        return estado
    try:
        async with httpx.AsyncClient(timeout=10.0) as cliente:
            respuesta = await cliente.get(
                f"{GEMINI_API_URL}/v1beta/models/{MODELO_ANALISIS}",
                headers={"X-Goog-Api-Key": GEMINI_API_KEY},
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
    except (httpx.HTTPError, ValueError):
        return estado
    metodos = datos.get("supportedGenerationMethods", [])
    estado["ok"] = "generateContent" in metodos
    return estado


async def estado_ollama() -> dict[str, Any]:
    """Comprueba el proveedor, los modelos requeridos y la capacidad de vision."""
    if PROVEEDOR == "gemini_api":
        return await _estado_gemini_api()
    try:
        async with httpx.AsyncClient(timeout=5.0) as cliente:
            respuesta = await cliente.get(f"{OLLAMA_URL}/api/tags")
            respuesta.raise_for_status()
            modelos = respuesta.json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return {
            "ok": False,
            "modelo": MODELO_ANALISIS,
            "modelo_vision": MODELO_VISION,
            "proveedor": "ollama",
            "ollama": False,
            "adaptador": ADAPTADOR_ACTIVO,
        }

    nombres = {
        modelo.get("name") or modelo.get("model")
        for modelo in modelos
        if isinstance(modelo, dict)
    }
    requeridos = {MODELO_VISION, MODELO_ANALISIS}
    disponibles = requeridos.issubset(nombres)
    vision = False
    if disponibles:
        try:
            async with httpx.AsyncClient(timeout=5.0) as cliente:
                detalle = await cliente.post(
                    f"{OLLAMA_URL}/api/show", json={"model": MODELO_VISION}
                )
                detalle.raise_for_status()
                vision = "vision" in detalle.json().get("capabilities", [])
        except (httpx.HTTPError, ValueError):
            vision = False
    return {
        "ok": disponibles and vision,
        "modelo": MODELO_ANALISIS,
        "modelo_vision": MODELO_VISION,
        "proveedor": "ollama",
        "ollama": True,
        "adaptador": ADAPTADOR_ACTIVO,
    }


if __name__ == "__main__":
    estado = asyncio.run(estado_ollama())
    print(estado)
    if not estado["ollama"]:
        print("Inicia Ollama con: ollama serve")
    elif not estado["ok"]:
        print(
            f"Verifica los modelos vision={MODELO_VISION} "
            f"y analisis={MODELO_ANALISIS}"
        )
