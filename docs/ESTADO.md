# Estado

Actualizado: 1 de agosto de 2026.

## Listo

- Backend FastAPI + LangGraph implementado.
- Frontend React integrado con los dos endpoints reales.
- Imagen: transcripcion visible, editable y reanalizable.
- Riesgo, puntaje, banderas, origen, explicacion y recomendacion.
- Estadisticas PNP-MININTER cargadas desde archivos locales.
- Ollama por `/api/chat`, `think:false` y `num_ctx=16384`.
- Errores controlados, CORS y health check.
- Modos mock y API para el frontend.
- Pruebas sin inferencia y build de produccion.

## Restriccion temporal

El entrenamiento esta activo fuera de este repositorio. No se debe ejecutar
Ollama ni probar inferencias hasta que el proceso libere la GPU. FastAPI y Vite
si pueden iniciarse para comprobar que la interfaz abre.

## Cierre de demo

1. Confirmar que el entrenamiento termino y la GPU esta libre.
2. Comprobar `GET /api/salud`.
3. Probar un aviso de texto bajo, medio y alto.
4. Probar una captura legible.
5. Grabar el flujo de 90 segundos.
