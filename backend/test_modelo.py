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

    def test_no_reintenta_ocr_cuando_ya_detecta_oferta(self):
        generar = AsyncMock(return_value="Estamos en busca de personal. Buen sueldo.")
        with patch.object(modelo, "_generar", generar):
            salida = asyncio.run(modelo.transcribir_imagen(b"imagen"))
        self.assertIn("busca de personal", salida)
        self.assertEqual(generar.await_count, 1)


if __name__ == "__main__":
    unittest.main()
