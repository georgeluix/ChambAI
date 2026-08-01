import { useEffect, useMemo, useRef, useState } from "react";
import {
  analizarAviso,
  analizarFoto,
  DISCLAIMER,
  obtenerEstadisticas,
} from "./services/analyzer.js";

const RIESGOS = {
  bajo: { etiqueta: "Riesgo bajo", nivel: 1, resumen: "No se ven alertas evidentes" },
  medio: { etiqueta: "Riesgo medio", nivel: 2, resumen: "Conviene verificar antes de responder" },
  alto: { etiqueta: "Riesgo alto", nivel: 3, resumen: "Detén la postulación y pide ayuda" },
};
const TIPOS_IMAGEN = new Set(["image/jpeg", "image/png", "image/webp"]);
const MAXIMO_IMAGEN = 10 * 1024 * 1024;

function IconoEscudo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 5.5 5.8v5.6c0 4.1 2.7 7.8 6.5 9.1 3.8-1.3 6.5-5 6.5-9.1V5.8L12 3Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function IconoCamara() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 8.5h3l1.3-2h7.4l1.3 2h3v10H4v-10Z" />
      <circle cx="12" cy="13.5" r="3.2" />
    </svg>
  );
}

function IconoNivelRiesgo({ riesgo }) {
  if (riesgo === "alto") {
    return (
      <span className="semaforo__icono semaforo__icono--alto" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path d="M12 3.7 21 20H3L12 3.7Z" />
          <path d="M12 9v5" />
          <circle cx="12" cy="17.2" r=".8" />
        </svg>
      </span>
    );
  }
  return (
    <span className={`semaforo__icono semaforo__icono--${riesgo}`} aria-hidden="true">
      {riesgo === "bajo" ? "✓" : "!"}
    </span>
  );
}

function EscalaRiesgo({ riesgo, puntaje }) {
  const actual = RIESGOS[riesgo];
  return (
    <div className={`escala escala--${riesgo}`}>
      <div className="escala__cabecera">
        <span>Puntaje orientativo</span>
        <strong>{puntaje}/100</strong>
      </div>
      <div
        className="barra-puntaje"
        role="progressbar"
        aria-label="Puntaje de señales de riesgo"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={puntaje}
      >
        <span style={{ width: `${puntaje}%` }} />
      </div>
      <div className="escala__etiquetas" aria-hidden="true">
        <span>Bajo</span><span>Medio</span><span>Alto · máximo</span>
      </div>
      <span className="sr-only">{actual.etiqueta}</span>
    </div>
  );
}

function Spinner({ modo }) {
  return (
    <div className="cargando" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div>
        <strong>{modo === "foto" ? "Leyendo y analizando la foto..." : "Analizando localmente..."}</strong>
        <span>{modo === "foto" ? "Gemma primero transcribe y luego analiza" : "El aviso no sale de tu equipo"}</span>
      </div>
    </div>
  );
}

function PanelEstadisticas({ estadisticas }) {
  const ficha = estadisticas?.ficha_nacional;
  if (!ficha) return null;
  return (
    <aside className="dato-nacional" aria-label="Contexto nacional verificable">
      <strong>{ficha.pct_captadas_por_oferta_de_trabajo}%</strong>
      <p>de las denuncias registradas entre 2017 y 2023 comenzaron con una oferta de trabajo.</p>
      <small>{ficha.denuncias_2017_2023} denuncias · {ficha.fuente}</small>
    </aside>
  );
}

function Resultados({ resultado, desdeFoto, onEditarTranscripcion }) {
  if (!resultado.aviso_detectado) {
    return (
      <section className="resultados resultado-sin-aviso" aria-live="polite">
        <div className="bloque">
          <h2>No encontramos un aviso de trabajo</h2>
          <p>{resultado.explicacion}</p>
          <p className="recomendacion">{resultado.recomendacion}</p>
          {desdeFoto && resultado.contexto_visual && (
            <div className="contexto-visual contexto-visual--interno">
              <strong>Lo que Gemma observó</strong>
              <p>{resultado.contexto_visual}</p>
            </div>
          )}
        </div>
      </section>
    );
  }

  const riesgo = RIESGOS[resultado.riesgo];
  return (
    <section className="resultados" aria-labelledby="resultado-titulo">
      <div className={`semaforo semaforo--${resultado.riesgo}`}>
        <div className="semaforo__encabezado">
          <IconoNivelRiesgo riesgo={resultado.riesgo} />
          <div>
            <p className="eyebrow">Resultado del análisis</p>
            <h2 id="resultado-titulo">{riesgo.etiqueta}</h2>
            <p className="semaforo__resumen">{riesgo.resumen}</p>
          </div>
        </div>
        <EscalaRiesgo riesgo={resultado.riesgo} puntaje={resultado.puntaje} />
      </div>

      <div className="bloque">
        <h3>Señales encontradas</h3>
        {resultado.banderas.length === 0 ? (
          <p className="sin-banderas">No se encontraron señales de alerta evidentes.</p>
        ) : (
          <ul className={`banderas banderas--${resultado.riesgo}`}>
            {resultado.banderas.map((bandera, indice) => (
              <li key={`${bandera.texto}-${indice}`}>
                <p className="bandera__tipo">{bandera.texto}</p>
                <div className="bandera__metadatos">
                  <span>{bandera.gravedad}</span>
                  <span className={`origen origen--${bandera.origen}`}>
                    {bandera.origen === "regla" ? "Regla verificable" : "Interpretación de Gemma"}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="bloque explicacion">
        <h3>¿Qué significa?</h3>
        <p>{resultado.explicacion}</p>
      </div>

      <div className={`bloque recomendacion recomendacion--${resultado.riesgo}`}>
        <h3>Qué hacer ahora</h3>
        <p>{resultado.recomendacion}</p>
      </div>

      {resultado.contexto_local?.frases?.length > 0 && (
        <div className="bloque contexto-local">
          <h3>Contexto local verificable</h3>
          <ul>{resultado.contexto_local.frases.map((frase) => <li key={frase}>{frase}</li>)}</ul>
          {resultado.contexto_local.fuente && (
            <small>Fuente: {resultado.contexto_local.fuente}</small>
          )}
        </div>
      )}

      {desdeFoto && resultado.contexto_visual && (
        <div className="bloque contexto-visual">
          <h3>Contexto visual observado</h3>
          <p>{resultado.contexto_visual}</p>
          <small>Descripción de Gemma basada en la foto; no es una conclusión legal.</small>
        </div>
      )}

      {desdeFoto && resultado.texto_analizado && (
        <div className="bloque transcripcion">
          <h3>Texto leído de la imagen</h3>
          <p>{resultado.texto_analizado}</p>
          <button type="button" className="boton-secundario" onClick={() => onEditarTranscripcion(resultado.texto_analizado)}>
            Corregir texto y volver a analizar
          </button>
        </div>
      )}

      {!resultado.formato_valido && (
        <div className="aviso-formato" role="alert">
          <strong>Gemma no respetó el formato esperado.</strong>
          <span>Se muestran las reglas seguras y puedes revisar la respuesta cruda.</span>
          {resultado.texto_crudo && <details><summary>Ver respuesta cruda</summary><pre>{resultado.texto_crudo}</pre></details>}
        </div>
      )}

      <p className="disclaimer">
        {DISCLAIMER} · Procesado en {resultado.tiempo_ms} ms.
      </p>
    </section>
  );
}

export default function App() {
  const [modo, setModo] = useState("foto");
  const [texto, setTexto] = useState("");
  const [foto, setFoto] = useState(null);
  const [fotoUrl, setFotoUrl] = useState("");
  const [estado, setEstado] = useState("inicial");
  const [resultado, setResultado] = useState(null);
  const [mensajeError, setMensajeError] = useState("");
  const [desdeFoto, setDesdeFoto] = useState(false);
  const [estadisticas, setEstadisticas] = useState(null);
  const resultadosRef = useRef(null);

  const procesando = estado === "cargando";
  const puedeAnalizar = modo === "texto" ? Boolean(texto.trim()) : Boolean(foto);
  const nombreFoto = useMemo(() => {
    if (!foto) return "";
    return foto.name.length > 34 ? `${foto.name.slice(0, 31)}...` : foto.name;
  }, [foto]);

  useEffect(() => {
    obtenerEstadisticas().then(setEstadisticas).catch(() => setEstadisticas(null));
  }, []);

  useEffect(() => () => { if (fotoUrl) URL.revokeObjectURL(fotoUrl); }, [fotoUrl]);
  useEffect(() => {
    if (estado === "exito") resultadosRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [estado]);

  function cambiarModo(nuevoModo) {
    if (procesando) return;
    setModo(nuevoModo);
    setEstado("inicial");
    setResultado(null);
    setMensajeError("");
  }

  function seleccionarFoto(evento) {
    const archivo = evento.target.files?.[0];
    if (!archivo) return;
    if (!TIPOS_IMAGEN.has(archivo.type)) {
      setMensajeError("Formato no permitido. Elige una imagen JPG, PNG o WEBP.");
      setEstado("error");
      return;
    }
    if (archivo.size > MAXIMO_IMAGEN) {
      setMensajeError("La imagen supera el límite de 10 MB. Comprímela e intenta de nuevo.");
      setEstado("error");
      return;
    }
    if (fotoUrl) URL.revokeObjectURL(fotoUrl);
    setFoto(archivo);
    setFotoUrl(URL.createObjectURL(archivo));
    setResultado(null);
    setEstado("inicial");
  }

  function quitarFoto() {
    if (fotoUrl) URL.revokeObjectURL(fotoUrl);
    setFoto(null);
    setFotoUrl("");
    setResultado(null);
    setEstado("inicial");
  }

  function editarTranscripcion(transcripcion) {
    setTexto(transcripcion === "SIN_AVISO" ? "" : transcripcion);
    setModo("texto");
    setResultado(null);
    setEstado("inicial");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function analizar(evento) {
    evento.preventDefault();
    if (!puedeAnalizar || procesando) return;
    setResultado(null);
    setMensajeError("");
    try {
      setEstado("cargando");
      const esFoto = modo === "foto";
      const datos = esFoto ? await analizarFoto(foto) : await analizarAviso(texto.trim());
      if (!RIESGOS[datos.riesgo] || !Array.isArray(datos.banderas) || typeof datos.puntaje !== "number") {
        throw new Error("El backend devolvió un formato inesperado.");
      }
      setDesdeFoto(esFoto);
      setResultado(datos);
      setEstado("exito");
    } catch (error) {
      setMensajeError(error instanceof Error ? error.message : "No se pudo completar el análisis.");
      setEstado("error");
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div className="marca"><IconoEscudo /></div>
        <div><p className="eyebrow">Tu seguridad empieza aquí</p><h1>ChambAI</h1><p className="subtitulo">Analiza ofertas antes de responder</p></div>
      </header>

      <PanelEstadisticas estadisticas={estadisticas} />

      <section className="panel" aria-labelledby="formulario-titulo">
        <div className="modo-selector" role="tablist" aria-label="Forma de ingresar el aviso">
          <button type="button" role="tab" aria-selected={modo === "foto"} className={modo === "foto" ? "activo" : ""} onClick={() => cambiarModo("foto")}>
            <IconoCamara /> Tomar foto
          </button>
          <button type="button" role="tab" aria-selected={modo === "texto"} className={modo === "texto" ? "activo" : ""} onClick={() => cambiarModo("texto")}>
            <span aria-hidden="true">Aa</span> Pegar texto
          </button>
        </div>

        <form onSubmit={analizar}>
          {modo === "foto" ? (
            <div className="entrada-foto" role="tabpanel">
              <div className="intro-entrada"><h2 id="formulario-titulo">Fotografía el aviso</h2><p>Procura que el texto se vea derecho, enfocado y con buena luz.</p></div>
              {fotoUrl ? (
                <div className="foto-seleccionada">
                  <img src={fotoUrl} alt="Aviso seleccionado para analizar" />
                  <div><span title={foto.name}>{nombreFoto}</span><button type="button" className="boton-texto" onClick={quitarFoto} disabled={procesando}>Cambiar foto</button></div>
                </div>
              ) : (
                <label className="capturar" htmlFor="foto-aviso"><span className="capturar__icono"><IconoCamara /></span><strong>Tomar o elegir una foto</strong><span>JPG, PNG o WEBP · máximo 10 MB</span></label>
              )}
              <input className="input-archivo" id="foto-aviso" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={seleccionarFoto} disabled={procesando} />
            </div>
          ) : (
            <div role="tabpanel">
              <label id="formulario-titulo" htmlFor="aviso">Pega o corrige el aviso</label>
              <p className="ayuda">Incluye el aviso completo para obtener un mejor análisis.</p>
              <textarea id="aviso" value={texto} onChange={(evento) => setTexto(evento.target.value)} placeholder="Ejemplo: Se busca personal con disponibilidad inmediata..." rows="8" disabled={procesando} />
            </div>
          )}

          <div className="privacidad"><span className="privacidad__luz" aria-hidden="true" /><div><strong>Privado y sin internet</strong><span>El aviso se procesa con Gemma en tu equipo; no se guarda</span></div></div>
          <button className="boton-principal" type="submit" disabled={!puedeAnalizar || procesando}>{procesando ? "Procesando..." : modo === "foto" ? "Analizar foto" : "Analizar aviso"}<span aria-hidden="true">→</span></button>
        </form>
      </section>

      {estado === "cargando" && <Spinner modo={modo} />}
      {estado === "error" && <div className="error" role="alert"><strong>No se pudo completar el análisis.</strong><span>{mensajeError}</span></div>}
      <div ref={resultadosRef}>{estado === "exito" && resultado && <Resultados resultado={resultado} desdeFoto={desdeFoto} onEditarTranscripcion={editarTranscripcion} />}</div>

      <footer className="pie-app"><IconoEscudo /><span>Funciona localmente con Gemma</span></footer>
    </main>
  );
}
