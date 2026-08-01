# Contrato de la API

## Texto

```http
POST /api/analizar
Content-Type: application/json
```

```json
{"texto":"Aviso laboral completo"}
```

## Imagen

```http
POST /api/analizar-imagen
Content-Type: multipart/form-data
```

Campo: `archivo`. Formatos: JPG, PNG o WEBP. Maximo: 10 MB.

## Respuesta de ambos endpoints

El siguiente bloque es JSONC para documentar cada campo; la respuesta real es
JSON estandar sin comentarios.

```jsonc
{
  "riesgo": "alto",              // bajo | medio | alto
  "puntaje": 50,                 // 0..100, suma ponderada de banderas
  "banderas": [
    {
      "texto": "Cobro adelantado al postulante", // frase canonica
      "gravedad": "critica",                       // leve | critica | grave
      "origen": "regla"                            // regla | modelo
    }
  ],
  "explicacion": "...",         // interpretacion preventiva de Gemma
  "recomendacion": "...",       // accion concreta segun el riesgo
  "contexto_local": {
    "departamentos_mencionados": ["LIMA"],
    "frases": ["Lima registra ..."],
    "fuente": "PNP - MININTER, Datos Abiertos del Estado Peruano"
  },
  "texto_analizado": "...",     // texto original o transcripcion editable
  "aviso_detectado": true,       // false si la foto no contiene un aviso
  "formato_valido": true,        // false si Gemma fallo tras el reintento
  "tiempo_ms": 1700,
  "texto_crudo": "..."           // opcional; solo ante formato invalido
}
```

## Otros endpoints

- `GET /api/estadisticas`: ficha nacional y top de departamentos.
- `GET /api/salud`: disponibilidad de Ollama, modelo y vision.

Errores controlados: `413` imagen grande, `415` formato invalido, `422` texto
vacio y `503` Ollama/modelo no disponible.
