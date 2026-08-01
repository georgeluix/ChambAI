# -*- coding: utf-8 -*-
"""Pruebas sin Ollama para las reglas que nunca pueden fallar en silencio."""

import json
import unittest
from pathlib import Path

from extractor import (
    aplicar_reglas,
    canonizar_bandera,
    detectar_cobro_postulante,
    detectar_menores,
    es_aviso_laboral,
    parsear_salida_modelo,
)


def ejemplos_evaluacion():
    """Usa el set reservado si existe; conserva regresiones al empaquetar la app."""
    ruta = Path(__file__).resolve().parent.parent / "entrenamiento" / "evaluacion.jsonl"
    if ruta.exists():
        return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]
    return [
        {
            "messages": [
                {"role": "user", "content": "Horario de 7:00 a 16:00. Sueldo S/ 1800."},
                {
                    "role": "assistant",
                    "content": "RIESGO: bajo\nBANDERAS:\n- Ninguna señal de alerta detectada\nEXPLICACION: Las condiciones son verificables.",
                },
            ]
        },
        {
            "messages": [
                {"role": "user", "content": "Turno nocturno. Sueldo a conversar."},
                {
                    "role": "assistant",
                    "content": "RIESGO: medio\nBANDERAS:\n- Trabajo en horario nocturno\nEXPLICACION: Conviene verificar las condiciones.",
                },
            ]
        },
    ]


class ReglasDeterministasTest(unittest.TestCase):
    def test_detecta_edades_de_menores(self):
        casos = (
            "Buscamos chicas desde los 16",
            "Convocatoria para personas de 16 a 25 años",
            "Se aceptan mayores de 15 años",
            "No importa si estudias secundaria",
            "Edad: 17",
        )
        for caso in casos:
            with self.subTest(caso=caso):
                self.assertTrue(detectar_menores(caso))

    def test_no_confunde_horarios_sueldos_ni_experiencia(self):
        casos = (
            "Horario de 7:00 a 16:00",
            "Banda salarial de S/ 1200 a S/ 1600",
            "Se requieren de 2 a 4 años de experiencia",
            "Estudiantes desde 2 ciclo",
            "Personas de 18 a 25 años",
        )
        for caso in casos:
            with self.subTest(caso=caso):
                self.assertFalse(detectar_menores(caso))

    def test_cobro_al_postulante(self):
        self.assertTrue(detectar_cobro_postulante("Deposita S/ 50 para el uniforme"))
        self.assertFalse(detectar_cobro_postulante("Sueldo S/ 1800 en planilla"))

    def test_reconoce_afiche_laboral_estilizado(self):
        transcripcion = (
            "LUXURY CLUB\nANFITRIONAS\nBUEN SUELDO FIJO\nCOMISIONES AL 40%\n"
            "EXCELENTE AMBIENTE LABORAL\nESCRIBENOS PARA MAS INFORMACION"
        )
        self.assertTrue(es_aviso_laboral(transcripcion))
        self.assertTrue(es_aviso_laboral("Estamos en busca de anfitrionas"))
        self.assertFalse(es_aviso_laboral("Menu del dia: arroz con pollo y refresco"))
        self.assertFalse(es_aviso_laboral("SIN_TEXTO"))

    def test_canoniza_variantes_historicas(self):
        self.assertEqual(
            canonizar_bandera("Empresa sin RUC visible en el aviso"),
            ("Empleador no identificado: sin razon social ni RUC verificable",),
        )
        self.assertEqual(canonizar_bandera("Bandera inventada por el modelo"), ())

    def test_set_evaluacion_no_tiene_falsos_altos_por_reglas(self):
        for numero, ejemplo in enumerate(ejemplos_evaluacion(), 1):
            esperado = ejemplo["messages"][1]["content"].splitlines()[0].split(": ")[1]
            reglas = aplicar_reglas(ejemplo["messages"][0]["content"])
            if esperado != "alto":
                self.assertIsNone(
                    reglas["riesgo_forzado"],
                    f"La linea {numero} fue forzada incorrectamente a alto",
                )

    def test_parser_acepta_todo_el_set_de_evaluacion(self):
        for ejemplo in ejemplos_evaluacion():
            respuesta = ejemplo["messages"][1]["content"]
            self.assertTrue(parsear_salida_modelo(respuesta)["formato_valido"])


if __name__ == "__main__":
    unittest.main()
