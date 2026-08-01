# -*- coding: utf-8 -*-
"""Pruebas del contrato HTTP sin iniciar Ollama."""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


RESULTADO = {
    "riesgo": "bajo",
    "puntaje": 0,
    "banderas": [],
    "explicacion": "No se observan señales de alerta.",
    "recomendacion": "Verifica los datos antes de postular.",
    "contexto_local": {"departamentos_mencionados": [], "frases": []},
    "texto_analizado": "Empresa formal con RUC.",
    "aviso_detectado": True,
    "formato_valido": True,
    "tiempo_ms": 12,
}


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.cliente = TestClient(main.app)

    def test_analizar_respeta_contrato(self):
        with patch.object(main, "ejecutar_texto", AsyncMock(return_value=RESULTADO)):
            respuesta = self.cliente.post(
                "/api/analizar", json={"texto": "Empresa formal con RUC."}
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), RESULTADO)

    def test_texto_vacio_es_error_controlado(self):
        respuesta = self.cliente.post("/api/analizar", json={"texto": "   "})
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("no puede estar vacio", respuesta.json()["detail"])

    def test_imagen_invalida_no_llega_al_modelo(self):
        respuesta = self.cliente.post(
            "/api/analizar-imagen",
            files={"archivo": ("aviso.png", b"no-es-png", "image/png")},
        )
        self.assertEqual(respuesta.status_code, 415)

    def test_estadisticas_usan_datos_procesados(self):
        respuesta = self.cliente.get("/api/estadisticas")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json()["ficha_nacional"]["pct_captadas_por_oferta_de_trabajo"],
            72.9,
        )

    def test_cors_local(self):
        respuesta = self.cliente.options(
            "/api/analizar",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.headers["access-control-allow-origin"], "http://localhost:5173"
        )


if __name__ == "__main__":
    unittest.main()
