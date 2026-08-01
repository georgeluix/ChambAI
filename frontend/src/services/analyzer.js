const API_BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const USA_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

export const DISCLAIMER =
  "Este análisis es orientativo. No determina delitos ni reemplaza la evaluación de las autoridades.";

function respuestaDemo(texto) {
  const alto = /deposita|yapea|menor(?:es)? de edad|desde los? 1[0-7]|retener.*dni/i.test(texto);
  const medio = /whatsapp|turno noche|sin contrato|sueldo.*entrevista/i.test(texto);
  const riesgo = alto ? "alto" : medio ? "medio" : "bajo";
  const banderas = alto
    ? [
        {
          texto: /deposita|yapea/i.test(texto)
            ? "Cobro adelantado al postulante"
            : "Convocatoria dirigida a menores de edad",
          gravedad: /deposita|yapea/i.test(texto) ? "critica" : "grave",
          origen: "regla",
        },
      ]
    : medio
      ? [{ texto: "Postulacion por mensajeria personal", gravedad: "leve", origen: "modelo" }]
      : [];

  return {
    riesgo,
    puntaje: alto ? 30 : medio ? 8 : 0,
    banderas,
    explicacion:
      riesgo === "alto"
        ? "El aviso contiene una señal que requiere detener la postulación y verificar su origen."
        : riesgo === "medio"
          ? "Faltan datos verificables antes de continuar con la postulación."
          : "El aviso presenta condiciones verificables y no muestra señales evidentes de captación.",
    recomendacion:
      riesgo === "alto"
        ? "No respondas ni entregues datos personales. Reporta el aviso a la Línea 1818 del MININTER."
        : "Verifica el RUC y las condiciones por escrito antes de postular.",
    contexto_local: { departamentos_mencionados: [], frases: [] },
    texto_analizado: texto,
    aviso_detectado: true,
    formato_valido: true,
    tiempo_ms: 950,
  };
}

async function leerRespuesta(respuesta) {
  let datos;
  try {
    datos = await respuesta.json();
  } catch {
    throw new Error("El backend devolvió una respuesta que no es JSON válido.");
  }
  if (!respuesta.ok) {
    throw new Error(datos.detail || `El backend respondió con estado ${respuesta.status}.`);
  }
  return datos;
}

export async function analizarAviso(texto) {
  if (USA_MOCKS) {
    await new Promise((resolver) => setTimeout(resolver, 700));
    return respuestaDemo(texto);
  }

  const respuesta = await fetch(`${API_BASE_URL}/api/analizar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });
  return leerRespuesta(respuesta);
}

export async function analizarFoto(imagen) {
  if (USA_MOCKS) {
    await new Promise((resolver) => setTimeout(resolver, 1000));
    const texto =
      "Buscamos chicas desde los 16 años. Deposita S/ 50 para separar tu vacante.";
    return respuestaDemo(texto);
  }

  const formulario = new FormData();
  formulario.append("archivo", imagen);
  const respuesta = await fetch(`${API_BASE_URL}/api/analizar-imagen`, {
    method: "POST",
    body: formulario,
  });
  return leerRespuesta(respuesta);
}

export async function obtenerEstadisticas() {
  if (USA_MOCKS) {
    return {
      ficha_nacional: {
        denuncias_2017_2023: 3822,
        pct_captadas_por_oferta_de_trabajo: 72.9,
        fuente: "PNP - MININTER, Datos Abiertos del Estado Peruano",
      },
      top_departamentos: [],
    };
  }
  const respuesta = await fetch(`${API_BASE_URL}/api/estadisticas`);
  return leerRespuesta(respuesta);
}
