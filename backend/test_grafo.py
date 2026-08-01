# -*- coding: utf-8 -*-
"""Pruebas del flujo completo sustituyendo Ollama por respuestas en memoria."""

import unittest
from unittest.mock import AsyncMock, patch

import grafo


class GrafoTest(unittest.IsolatedAsyncioTestCase):
    async def test_regla_gana_sobre_modelo(self):
        salida = (
            "RIESGO: bajo\nBANDERAS:\n- Ninguna señal de alerta detectada\n"
            "EXPLICACION: No se observan alertas."
        )
        with patch.object(grafo, "analizar_aviso", AsyncMock(return_value=salida)):
            resultado = await grafo.ejecutar_texto(
                "Buscamos chicas desde los 16 años. Deposita S/ 50 para el uniforme."
            )
        self.assertEqual(resultado["riesgo"], "alto")
        self.assertEqual(resultado["puntaje"], 50)
        self.assertTrue(all(b["origen"] == "regla" for b in resultado["banderas"]))

    async def test_reintento_y_texto_crudo(self):
        respuestas = AsyncMock(side_effect=["FORMATO ROTO", "OTRA VEZ ROTO"])
        with patch.object(grafo, "analizar_aviso", respuestas):
            resultado = await grafo.ejecutar_texto("Trabajo sin sueldo indicado.")
        self.assertFalse(resultado["formato_valido"])
        self.assertEqual(resultado["texto_crudo"], "OTRA VEZ ROTO")
        self.assertEqual(respuestas.await_count, 2)

    async def test_imagen_sin_aviso(self):
        with patch.object(
            grafo, "transcribir_imagen", AsyncMock(return_value="SIN_TEXTO")
        ):
            resultado = await grafo.ejecutar_imagen(b"imagen-simulada")
        self.assertFalse(resultado["aviso_detectado"])
        self.assertEqual(resultado["texto_analizado"], "SIN_TEXTO")

    async def test_imagen_estilizada_continua_al_analisis(self):
        transcripcion = (
            "LUXURY CLUB\nANFITRIONAS\nBUEN SUELDO FIJO\n"
            "COMISIONES AL 40%\nEXCELENTE AMBIENTE LABORAL"
        )
        salida = (
            "RIESGO: medio\nBANDERAS:\n- Remuneracion no especificada en el aviso\n"
            "EXPLICACION: Conviene verificar la identidad del empleador."
        )
        with (
            patch.object(grafo, "transcribir_imagen", AsyncMock(return_value=transcripcion)),
            patch.object(grafo, "analizar_aviso", AsyncMock(return_value=salida)),
        ):
            resultado = await grafo.ejecutar_imagen(b"imagen-simulada")
        self.assertTrue(resultado["aviso_detectado"])
        self.assertEqual(resultado["texto_analizado"], transcripcion)
        self.assertEqual(resultado["riesgo"], "medio")

    async def test_canoniza_bandera_del_corpus(self):
        salida = (
            "RIESGO: medio\nBANDERAS:\n- Empresa sin RUC visible en el aviso\n"
            "EXPLICACION: Conviene verificar la empresa."
        )
        with patch.object(grafo, "analizar_aviso", AsyncMock(return_value=salida)):
            resultado = await grafo.ejecutar_texto("Empresa ofrece trabajo por internet.")
        self.assertEqual(
            resultado["banderas"][0]["texto"],
            "Empleador no identificado: sin razon social ni RUC verificable",
        )
        self.assertEqual(resultado["banderas"][0]["gravedad"], "critica")

    async def test_descarta_bandera_fuera_del_catalogo(self):
        salida = (
            "RIESGO: medio\nBANDERAS:\n- Suposicion no respaldada por el aviso\n"
            "EXPLICACION: El modelo genero una etiqueta ajena al contrato."
        )
        with patch.object(grafo, "analizar_aviso", AsyncMock(return_value=salida)):
            resultado = await grafo.ejecutar_texto("Empresa identificada busca contador.")
        self.assertEqual(resultado["banderas"], [])
        self.assertEqual(resultado["riesgo"], "bajo")
        self.assertEqual(resultado["puntaje"], 0)
        self.assertFalse(resultado["formato_valido"])


if __name__ == "__main__":
    unittest.main()
