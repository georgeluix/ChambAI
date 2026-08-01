# -*- coding: utf-8 -*-
"""API HTTP de Chamba Segura."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from contexto import estadisticas_publicas
from grafo import ejecutar_imagen, ejecutar_texto
from modelo import OllamaNoDisponible, estado_ollama


MAXIMO_IMAGEN = 10 * 1024 * 1024
TIPOS_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp"}
ORIGENES_CORS = [
    origen.strip()
    for origen in os.getenv(
        "CHAMBA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origen.strip()
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chamba_segura")

app = FastAPI(title="Chamba Segura", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_CORS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SolicitudAnalisis(BaseModel):
    texto: str


def _es_imagen_real(contenido: bytes) -> bool:
    es_jpeg = contenido.startswith(b"\xff\xd8\xff")
    es_png = contenido.startswith(b"\x89PNG\r\n\x1a\n")
    es_webp = (
        len(contenido) >= 12
        and contenido.startswith(b"RIFF")
        and contenido[8:12] == b"WEBP"
    )
    return es_jpeg or es_png or es_webp


def _registrar_resultado(resultado: dict[str, Any]) -> None:
    # Nunca se registra el aviso ni los telefonos que pudiera contener.
    logger.info(
        "Analisis completado riesgo=%s tiempo_ms=%s",
        resultado["riesgo"],
        resultado["tiempo_ms"],
    )


@app.post("/api/analizar")
async def analizar_texto(solicitud: SolicitudAnalisis) -> dict[str, Any]:
    texto = solicitud.texto.strip()
    if not texto:
        raise HTTPException(
            status_code=422,
            detail="El campo 'texto' no puede estar vacio. Pega un aviso de trabajo.",
        )
    try:
        resultado = await ejecutar_texto(texto)
    except OllamaNoDisponible as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    _registrar_resultado(resultado)
    return resultado


@app.post("/api/analizar-imagen")
async def analizar_imagen(archivo: UploadFile = File(...)) -> dict[str, Any]:
    extension = Path(archivo.filename or "").suffix.lower()
    tipo_declarado = archivo.content_type or ""
    if tipo_declarado not in TIPOS_PERMITIDOS and extension not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=415,
            detail="Formato no permitido. Envia una imagen JPG, PNG o WEBP.",
        )

    try:
        contenido = await archivo.read(MAXIMO_IMAGEN + 1)
    finally:
        await archivo.close()

    if not contenido:
        raise HTTPException(status_code=400, detail="La imagen enviada esta vacia.")
    if len(contenido) > MAXIMO_IMAGEN:
        raise HTTPException(
            status_code=413,
            detail="La imagen supera el limite de 10 MB. Comprimela e intenta de nuevo.",
        )
    if not _es_imagen_real(contenido):
        raise HTTPException(
            status_code=415,
            detail="El archivo no contiene una imagen JPG, PNG o WEBP valida.",
        )

    try:
        resultado = await ejecutar_imagen(contenido)
    except OllamaNoDisponible as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    _registrar_resultado(resultado)
    return resultado


@app.get("/api/estadisticas")
async def estadisticas() -> dict[str, Any]:
    return estadisticas_publicas()


@app.get("/api/salud")
async def salud() -> JSONResponse:
    estado = await estado_ollama()
    codigo = 200 if estado["ok"] else 503
    return JSONResponse(status_code=codigo, content=estado)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000)
