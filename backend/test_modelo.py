# -*- coding: utf-8 -*-
"""Pruebas del contrato crítico entre el backend y Ollama."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

import modelo


class _ClienteFalso:
    ultima_url = None
    ultimo_json = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json):
        type(self).ultima_url = url
        type(self).ultimo_json = json
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "respuesta"}},
            request=httpx.Request("POST", url),
        )


class _ClienteGeminiFalso:
    ultima_url = None
    ultimos_headers = None
    ultimo_json = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers, json):
        type(self).ultima_url = url
        type(self).ultimos_headers = headers
        type(self).ultimo_json = json
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "respuesta hospedada"}]}}
                ]
            },
            request=httpx.Request("POST", url),
        )


class ModeloOllamaTest(unittest.TestCase):
    def test_chat_sin_thinking_y_con_contexto_completo(self):
        with patch.object(modelo.httpx, "AsyncClient", _ClienteFalso):
            salida = asyncio.run(
                modelo._generar(
                    "gemma4:e2b",
                    "Analiza este aviso",
                    imagen=b"imagen",
                    num_predict=32,
                )
            )

        self.assertEqual(salida, "respuesta")
        self.assertTrue(_ClienteFalso.ultima_url.endswith("/api/chat"))
        cuerpo = _ClienteFalso.ultimo_json
        self.assertIs(cuerpo["think"], False)
        self.assertEqual(cuerpo["options"]["num_ctx"], 16384)
        self.assertEqual(cuerpo["messages"][0]["role"], "user")
        self.assertIn("images", cuerpo["messages"][0])
        self.assertNotIn("prompt", cuerpo)

    def test_gemini_api_envia_imagen_y_desactiva_thinking_extenso(self):
        png = b"\x89PNG\r\n\x1a\ncontenido"
        with (
            patch.object(modelo, "PROVEEDOR", "gemini_api"),
            patch.object(modelo, "GEMINI_API_KEY", "clave-de-prueba"),
            patch.object(modelo.httpx, "AsyncClient", _ClienteGeminiFalso),
        ):
            salida = asyncio.run(
                modelo._generar(
                    "gemma-4-26b-a4b-it",
                    "Lee el aviso",
                    imagen=png,
                    num_predict=64,
                )
            )

        self.assertEqual(salida, "respuesta hospedada")
        self.assertIn("gemma-4-26b-a4b-it:generateContent", _ClienteGeminiFalso.ultima_url)
        self.assertEqual(
            _ClienteGeminiFalso.ultimos_headers["X-Goog-Api-Key"],
            "clave-de-prueba",
        )
        cuerpo = _ClienteGeminiFalso.ultimo_json
        parte_imagen = cuerpo["contents"][0]["parts"][0]["inlineData"]
        self.assertEqual(parte_imagen["mimeType"], "image/png")
        self.assertEqual(
            cuerpo["generationConfig"]["thinkingConfig"]["thinkingLevel"],
            "minimal",
        )

    def test_reintenta_ocr_si_la_primera_lectura_no_parece_aviso(self):
        generar = AsyncMock(
            side_effect=[
                "SIN_AVISO",
                "LUXURY CLUB\nANFITRIONAS\nBUEN SUELDO\nCOMISIONES AL 40%",
            ]
        )
        with patch.object(modelo, "_generar", generar):
            salida = asyncio.run(modelo.transcribir_imagen(b"imagen"))
        self.assertIn("ANFITRIONAS", salida)
        self.assertEqual(generar.await_count, 2)

    def test_separa_texto_y_contexto_visual(self):
        salida = (
            "**TEXTO_VISIBLE:**\nLUXURY CLUB\nANFITRIONAS\n\n"
            "**CONTEXTO_VISUAL:** Club nocturno con bebidas y dos mujeres."
        )
        extraccion = modelo._parsear_extraccion_visual(salida)
        self.assertIn("ANFITRIONAS", extraccion["texto"])
        self.assertIn("Club nocturno", extraccion["contexto_visual"])

    def test_vision_usa_modelo_separado(self):
        generar = AsyncMock(
            return_value=(
                "TEXTO_VISIBLE:\nBuscamos personal\n"
                "CONTEXTO_VISUAL:\nAviso sobre un local."
            )
        )
        with patch.object(modelo, "_generar", generar):
            asyncio.run(modelo.extraer_imagen(b"imagen"))
        self.assertEqual(generar.await_args.args[0], modelo.MODELO_VISION)

    def test_no_reintenta_ocr_cuando_ya_detecta_oferta(self):
        generar = AsyncMock(return_value="Estamos en busca de personal. Buen sueldo.")
        with patch.object(modelo, "_generar", generar):
            salida = asyncio.run(modelo.transcribir_imagen(b"imagen"))
        self.assertIn("busca de personal", salida)
        self.assertEqual(generar.await_count, 1)


if __name__ == "__main__":
    unittest.main()
