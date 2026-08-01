import { useEffect, useMemo, useRef, useState } from "react";
import { analizarAviso, analizarFoto } from "./services/analyzer.js";

const RIESGOS = {
  bajo: { etiqueta: "Riesgo bajo", nivel: 1, resumen: "No se ven alertas evidentes" },
  medio: { etiqueta: "Riesgo medio", nivel: 2, resumen: "Conviene verificar antes de responder" },
  alto: { etiqueta: "Riesgo alto", nivel: 3, resumen: "Es el nivel de peligro máximo" },
};

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

function EscalaRiesgo({ riesgo }) {
  const actual = RIESGOS[riesgo];
  const niveles = ["bajo", "medio", "alto"];

  return (
    <div
      className={`escala escala--${riesgo}`}
      role="img"
      aria-label={`${actual.etiqueta}: nivel ${actual.nivel} de 3`}
    >
      <div className="escala__barras" aria-hidden="true">
        {niveles.map((nivel, indice) => (
          <span
            key={nivel}
            className={`escala__barra ${indice < actual.nivel ? "activa" : ""}`}
          />
        ))}
      </div>
      <div className="escala__etiquetas" aria-hidden="true">
        <span>Bajo</span>
        <span>Medio</span>
        <span>Alto · máximo</span>
      </div>
    </div>
  );
}

function Spinner({ modo }) {
  return (
    <div className="cargando" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div>
        <strong>{modo === "foto" ? "Procesando foto localmente..." : "Analizando localmente..."}</strong>
        {modo === "foto" && <span>El backend local está leyendo el aviso</span>}
      </div>
    </div>
  );
}

function Resultados({ resultado }) {
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
        <EscalaRiesgo riesgo={resultado.riesgo} />
      </div>

      <div className="bloque">
        <h3>Señales encontradas</h3>
        {resultado.banderas.length === 0 ? (
          <p className="sin-banderas">No se encontraron señales de alerta evidentes.</p>
        ) : (
          <ul className={`banderas banderas--${resultado.riesgo}`}>
            {resultado.banderas.map((bandera, indice) => (
              <li key={`${bandera.tipo}-${indice}`}>
                <p className="bandera__tipo">{bandera.tipo}</p>
                <p>{bandera.descripcion}</p>
                {bandera.fragmento && (
                  <blockquote>
                    <mark>{bandera.fragmento}</mark>
                  </blockquote>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="bloque explicacion">
        <h3>¿Qué significa?</h3>
        <p>{resultado.explicacion}</p>
      </div>

      <p className="disclaimer">{resultado.disclaimer}</p>
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
  const resultadosRef = useRef(null);

  const procesando = estado === "cargando";
  const puedeAnalizar = modo === "texto" ? Boolean(texto.trim()) : Boolean(foto);

  useEffect(() => {
    return () => {
      if (fotoUrl) URL.revokeObjectURL(fotoUrl);
    };
  }, [fotoUrl]);

  useEffect(() => {
    if (estado === "exito") {
      resultadosRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [estado]);

  const nombreFoto = useMemo(() => {
    if (!foto) return "";
    return foto.name.length > 34 ? `${foto.name.slice(0, 31)}...` : foto.name;
  }, [foto]);

  function cambiarModo(nuevoModo) {
    if (procesando) return;
    setModo(nuevoModo);
    setEstado("inicial");
    setResultado(null);
  }

  function seleccionarFoto(evento) {
    const archivo = evento.target.files?.[0];
    if (!archivo) return;

    if (!archivo.type.startsWith("image/")) {
      setEstado("error_foto");
      return;
    }

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

  async function analizar(evento) {
    evento.preventDefault();
    if (!puedeAnalizar || procesando) return;

    setResultado(null);
    try {
      setEstado("cargando");
      const datos = modo === "foto"
        ? await analizarFoto(foto)
        : await analizarAviso(texto.trim());

      if (!RIESGOS[datos.riesgo] || !Array.isArray(datos.banderas)) {
        throw new Error("Formato de respuesta inesperado");
      }

      setResultado(datos);
      setEstado("exito");
    } catch (error) {
      console.error("No se pudo completar el análisis:", error);
      setEstado("error");
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div className="marca"><IconoEscudo /></div>
        <div>
          <p className="eyebrow">Tu seguridad empieza aquí</p>
          <h1>ChambAI</h1>
          <p className="subtitulo">Analiza ofertas antes de responder</p>
        </div>
      </header>

      <section className="panel" aria-labelledby="formulario-titulo">
        <div className="modo-selector" role="tablist" aria-label="Forma de ingresar el aviso">
          <button
            type="button"
            role="tab"
            aria-selected={modo === "foto"}
            className={modo === "foto" ? "activo" : ""}
            onClick={() => cambiarModo("foto")}
          >
            <IconoCamara /> Tomar foto
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={modo === "texto"}
            className={modo === "texto" ? "activo" : ""}
            onClick={() => cambiarModo("texto")}
          >
            <span aria-hidden="true">Aa</span> Pegar texto
          </button>
        </div>

        <form onSubmit={analizar}>
          {modo === "foto" ? (
            <div className="entrada-foto" role="tabpanel">
              <div className="intro-entrada">
                <h2 id="formulario-titulo">Fotografía el aviso</h2>
                <p>Procura que el texto se vea derecho, enfocado y con buena luz.</p>
              </div>

              {fotoUrl ? (
                <div className="foto-seleccionada">
                  <img src={fotoUrl} alt="Aviso seleccionado para analizar" />
                  <div>
                    <span title={foto.name}>{nombreFoto}</span>
                    <button type="button" className="boton-texto" onClick={quitarFoto} disabled={procesando}>
                      Cambiar foto
                    </button>
                  </div>
                </div>
              ) : (
                <label className="capturar" htmlFor="foto-aviso">
                  <span className="capturar__icono"><IconoCamara /></span>
                  <strong>Tomar o elegir una foto</strong>
                  <span>JPG, PNG o imagen de tu galería</span>
                </label>
              )}

              <input
                className="input-archivo"
                id="foto-aviso"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={seleccionarFoto}
                disabled={procesando}
              />
            </div>
          ) : (
            <div role="tabpanel">
              <label id="formulario-titulo" htmlFor="aviso">Pega el mensaje que recibiste</label>
              <p className="ayuda">Incluye el aviso completo para obtener un mejor análisis.</p>
              <textarea
                id="aviso"
                value={texto}
                onChange={(evento) => setTexto(evento.target.value)}
                placeholder="Ejemplo: Se busca personal con disponibilidad inmediata..."
                rows="8"
                disabled={procesando}
              />
            </div>
          )}

          <div className="privacidad">
            <span className="privacidad__luz" aria-hidden="true" />
            <div>
              <strong>Privado y sin internet</strong>
              <span>La foto se procesa en el backend local, sin servicios externos</span>
            </div>
          </div>

          <button className="boton-principal" type="submit" disabled={!puedeAnalizar || procesando}>
            {procesando ? "Procesando..." : modo === "foto" ? "Analizar foto" : "Analizar aviso"}
            <span aria-hidden="true">→</span>
          </button>
        </form>
      </section>

      {estado === "cargando" && <Spinner modo={modo} />}

      {estado === "error" && (
        <div className="error" role="alert">
          <strong>No se pudo completar el análisis.</strong>
          <span>Si usas el backend, verifica que esté corriendo en el puerto 8000.</span>
        </div>
      )}

      <div ref={resultadosRef}>
        {estado === "exito" && resultado && (
          <Resultados resultado={resultado} />
        )}
      </div>

      <footer className="pie-app">
        <IconoEscudo />
        <span>Funciona sin internet</span>
      </footer>
    </main>
  );
}
