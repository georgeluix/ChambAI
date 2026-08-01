# Estado del proyecto

Última actualización: 1 de agosto de 2026.

Este archivo es la bitácora breve para retomar el trabajo después de un reinicio o desde otro chat. Debe actualizarse cuando cambie el estado del proyecto.

## Resumen

Estado general: **frontend implementado, dependencias instaladas y build verificado; backend pendiente**.

## Completado

- Proyecto React + Vite creado en la raíz.
- Pantalla única de ChambAI.
- Caja grande para pegar un aviso.
- Botón `Analizar` con bloqueo durante la solicitud.
- Indicador de análisis 100 % local.
- Solicitud `POST http://localhost:8000/analyze` con el contrato acordado.
- Presentación de riesgo bajo, medio y alto mediante texto, icono y color.
- Lista de banderas con fragmentos resaltados.
- Presentación de explicación y disclaimer.
- Estado de carga: `Analizando localmente...`.
- Mensaje de error para backend no disponible.
- Validación básica de entrada y respuesta.
- Diseño responsive, alto contraste y soporte de reducción de movimiento.
- Eliminación de fuentes y recursos externos para preservar el funcionamiento offline.
- Dependencias de npm instaladas: 26 paquetes y 0 vulnerabilidades reportadas.
- Build de producción verificado correctamente con Vite 8.2.0.
- Modo demo local agregado para desarrollar los tres niveles de riesgo sin backend.
- Captura o selección de fotos añadida con `capture="environment"` para cámara trasera.
- Envío de fotos preparado mediante `POST /analyze-image` y campo multipart `imagen`.
- OCR asignado al backend local; Tesseract.js y sus recursos fueron retirados del frontend.
- Escala visual de riesgo de tres niveles añadida; riesgo alto se identifica como nivel máximo.
- Interfaz reajustada como app móvil de 560 px máximo y pantalla completa en teléfonos.
- Iconos de riesgo diferenciados: círculo para medio y triángulo de alarma para alto.
- Etiqueta `Resultado del análisis` cambiada a azul grisáceo neutral.
- Escala acumulada ajustada para usar únicamente el color del riesgo obtenido.
- Marcos de las señales vinculados al riesgo: verde, amarillo o rojo.
- Títulos y citas de las señales vinculados a la misma paleta del riesgo.
- Nombre del producto actualizado de Chamba Segura a ChambAI.

## Pendiente inmediato

1. Reiniciar la terminal para que reciba el `PATH` actualizado.
2. Instalar Ollama y confirmar su disponibilidad con `ollama --version`.
3. Instalar o descargar el modelo local y confirmar su identificador con `ollama list`.
4. Probar visualmente el frontend con `npm run dev` (demo) y `npm run dev:api` (integración).
5. Crear el backend FastAPI.
6. Implementar el grafo mínimo de LangGraph.
7. Conectar Ollama con `num_ctx=16384` explícito.
8. Probar los tres niveles de riesgo y los estados de error.

## Estado de las herramientas

- Node.js 24.18.1: instalado en `C:\Program Files\nodejs`, aún no visible en el `PATH` de la terminal antigua.
- npm 11.16.0: instalado y utilizado mediante su ruta absoluta.
- Python 3.12.2: instalado, pero la terminal antigua resuelve primero el alias no funcional de Microsoft Store.
- Ollama: no encontrado en el `PATH` ni en sus ubicaciones habituales al realizar la verificación.
- Frontend: `npm install` y `npm run build` completados correctamente.

## Verificación después de reiniciar

Ejecutar desde la raíz del proyecto:

```bash
node --version
npm --version
python --version
ollama --version
ollama list
```

Después:

```bash
npm install
npm run build
npm run dev
```

No asumir que el nombre del modelo es correcto hasta comprobar `ollama list`.

## Pruebas mínimas del frontend

- El botón está deshabilitado con texto vacío.
- El botón envía exactamente `{ "texto": "..." }`.
- Se muestra el spinner mientras espera.
- Se muestra el error acordado cuando FastAPI no responde.
- Cada valor de riesgo usa el semáforo correcto.
- Una lista vacía de banderas se muestra correctamente.
- Los fragmentos aparecen resaltados.
- La interfaz funciona a 320 px de ancho.
- No se realizan solicitudes a dominios externos.
- Una foto tomada desde móvil se envía en el campo `imagen` al endpoint local acordado.
- El nivel alto se entiende como el máximo de la escala sin depender solo del color.

## Pruebas mínimas de integración

- FastAPI responde en el puerto 8000.
- CORS permite el origen local de Vite.
- La respuesta cumple el esquema incluso si el modelo genera texto inválido.
- Ollama funciona sin internet.
- Cada llamada a Ollama configura `num_ctx=16384`.
- El sistema no registra ni transmite fuera del equipo el aviso pegado.

## Registro de decisiones

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-08-01 | Stack fijo: React/Vite, FastAPI, LangGraph y Ollama | Requisito del hackathon |
| 2026-08-01 | Todo el análisis debe funcionar offline | Propuesta central de privacidad |
| 2026-08-01 | Usar siempre `num_ctx=16384` | Requisito técnico del equipo |
| 2026-08-01 | Comunicar niveles de riesgo, no culpabilidad | Uso responsable y alcance orientativo |
| 2026-08-01 | Tratar la cifra del 74 % como preliminar | Falta verificar la fuente exacta de MININTER |
| 2026-08-01 | Asignar OCR de fotografías al backend local | Evitar duplicar procesamiento y mantener React liviano |
| 2026-08-01 | Crear `POST /analyze-image` con campo `imagen` | Separar el contrato multipart del contrato JSON de texto |
| 2026-08-01 | Mantener ancho de app móvil en escritorio | La experiencia principal es captura en teléfono |
| 2026-08-01 | Renombrar el producto a ChambAI | Decisión de identidad del equipo |
| 2026-08-01 | Usar un solo color por resultado en la escala y banderas | Evitar que el verde sugiera seguridad en riesgos medio o alto |

## Limitación móvil conocida

La cámara y la interfaz pueden funcionar en el teléfono sin internet. El OCR y el análisis con Gemma/Ollama requieren conexión al equipo local que ejecuta el backend. Una experiencia autónoma fuera del alcance de esa red exigiría portar el modelo y su runtime al teléfono, fuera del stack fijado para este hackathon.

## Cómo cerrar una sesión

Antes de reiniciar o cambiar de chat:

1. Actualizar las secciones `Completado` y `Pendiente inmediato`.
2. Registrar decisiones nuevas en la tabla anterior.
3. Anotar comandos que fallaron y su mensaje relevante.
4. Guardar los archivos y, si Git está configurado, crear un commit descriptivo.

## Mensaje para un chat nuevo

```text
Continuemos ChambAI desde el estado actual. Revisa README.md,
docs/ARQUITECTURA.md y docs/ESTADO.md antes de actuar. El sistema debe
funcionar offline. Respeta exactamente el contrato de POST /analyze y usa
siempre num_ctx=16384 al conectar con Ollama. Código simple y funcional,
con comentarios en español. Luego continúa desde “Pendiente inmediato”.
```
