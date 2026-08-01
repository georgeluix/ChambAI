const API_URL = "http://localhost:8000/analyze";
const API_IMAGE_URL = "http://localhost:8000/analyze-image";

const DISCLAIMER =
  "Este análisis es orientativo y no constituye una denuncia ni una determinación legal.";

function obtenerFragmento(texto, patron) {
  const lineas = texto.split(/[\n.!?]+/).map((linea) => linea.trim()).filter(Boolean);
  const linea = lineas.find((candidata) => patron.test(candidata));
  return (linea || texto).slice(0, 120);
}

function crearRespuestaDemo(texto) {
  // El demo usa reglas transparentes; el análisis real lo realizará el backend local.
  const alertasAltas = [
    {
      patron: /dep[oó]sita|pago previo|paga(?:r)? (?:s\/|antes)|separa(?:r)? (?:tu )?vacante/i,
      tipo: "Solicitud de dinero",
      descripcion: "La oferta exige un pago antes de iniciar el supuesto trabajo.",
    },
    {
      patron: /viaje hoy|viajar de inmediato|traslado inmediato|documento original|retener/i,
      tipo: "Traslado o control de documentos",
      descripcion: "Se propone un traslado apresurado o entregar documentos sin condiciones verificables.",
    },
  ];

  const alertasMedias = [
    {
      patron: /disponibilidad inmediata|empresa importante|sin experiencia|whatsapp/i,
      tipo: "Información incompleta",
      descripcion: "El aviso utiliza condiciones generales que conviene verificar antes de responder.",
    },
  ];

  const altasEncontradas = alertasAltas
    .filter(({ patron }) => patron.test(texto))
    .map(({ patron, tipo, descripcion }) => ({
      tipo,
      descripcion,
      fragmento: obtenerFragmento(texto, patron),
    }));

  if (altasEncontradas.length > 0) {
    return {
      riesgo: "alto",
      banderas: altasEncontradas,
      explicacion:
        "Se encontraron señales de riesgo importantes. No envíes dinero ni documentos y verifica la oferta mediante canales independientes.",
      disclaimer: DISCLAIMER,
    };
  }

  const mediasEncontradas = alertasMedias
    .filter(({ patron }) => patron.test(texto))
    .map(({ patron, tipo, descripcion }) => ({
      tipo,
      descripcion,
      fragmento: obtenerFragmento(texto, patron),
    }));

  if (mediasEncontradas.length > 0) {
    return {
      riesgo: "medio",
      banderas: mediasEncontradas,
      explicacion:
        "La información disponible requiere cautela. Solicita datos formales de la empresa antes de continuar.",
      disclaimer: DISCLAIMER,
    };
  }

  return {
    riesgo: "bajo",
    banderas: [],
    explicacion:
      "No se encontraron señales de alerta evidentes. Aun así, verifica la identidad y los datos de la empresa antes de compartir información personal.",
    disclaimer: DISCLAIMER,
  };
}

export async function analizarAviso(texto) {
  if (import.meta.env.VITE_USE_MOCKS === "true") {
    // La pausa breve permite probar el estado de carga de la interfaz.
    await new Promise((resolver) => setTimeout(resolver, 900));
    return crearRespuestaDemo(texto);
  }

  const respuesta = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });

  if (!respuesta.ok) throw new Error("Respuesta no válida del backend");
  return respuesta.json();
}

export async function analizarFoto(imagen) {
  if (import.meta.env.VITE_USE_MOCKS === "true") {
    // El demo no hace OCR: simula la respuesta que entregará el backend local.
    await new Promise((resolver) => setTimeout(resolver, 1200));
    return {
      riesgo: "alto",
      banderas: [
        {
          tipo: "Solicitud de dinero",
          descripcion: "La oferta exige un pago antes de iniciar el supuesto trabajo.",
          fragmento: "Deposita S/ 50 para separar tu vacante",
        },
        {
          tipo: "Traslado apresurado",
          descripcion: "Se propone viajar de inmediato sin condiciones verificables.",
          fragmento: "Viaje hoy mismo, nosotros coordinamos todo",
        },
      ],
      explicacion:
        "Se encontraron señales de riesgo importantes. No envíes dinero ni documentos y verifica la oferta mediante canales independientes.",
      disclaimer: DISCLAIMER,
    };
  }

  const formulario = new FormData();
  formulario.append("imagen", imagen);

  const respuesta = await fetch(API_IMAGE_URL, {
    method: "POST",
    body: formulario,
  });

  if (!respuesta.ok) throw new Error("Respuesta no válida del backend");
  return respuesta.json();
}
