# -*- coding: utf-8 -*-
"""Normaliza los avisos recolectados para que encajen con el corpus sintetico.

La investigacion externa devuelve avisos reales valiosos, pero con tres
desviaciones que rompen la consistencia del entrenamiento:

1. BANDERAS con etiquetas cortas propias ("- informalidad", "- ninguna") en vez
   de las frases del catalogo. Mezclado con el corpus sintetico, el modelo
   aprende dos estilos y alterna entre ellos: el frontend no puede parsear.
2. Falta el prefijo "Analiza este aviso de empleo:" en el mensaje del usuario.
3. Entran registros tipo "ilustrativo" que NO son avisos de trabajo, sino
   cronicas periodisticas, resoluciones judiciales o consejos de campanas de
   prevencion. Si se entrena con ellos, el modelo aprende a clasificar el genero
   del texto ("esto habla de trata") en vez de evaluar una oferta laboral.
   Un consejo preventivo etiquetado "alto" es la inversion del significado.

Se conservan en el archivo crudo para trazabilidad del repositorio; aqui solo
se filtran del set de entrenamiento.

Uso:
  python normalizar_avisos.py avisos-reales-crudo.jsonl avisos-reales.jsonl
"""
import json
import re
import sys

PREFIJO = "Analiza este aviso de empleo:\n\n"

# etiqueta suelta de la investigacion -> frase del catalogo del corpus
CATALOGO = {
    "nocturno/privado": "Servicios de acompañamiento en local privado y horario nocturno",
    "entorno privado (sauna)": "Trabajo en local privado de acceso restringido",
    "establecimiento nocturno informal": "Servicios de acompañamiento en local privado y horario nocturno",
    "trabajo en bares y cantinas informales": "Servicios de acompañamiento en local privado y horario nocturno",
    "filtro de género": "Filtro por sexo y edad sin relacion con la funcion",
    "filtro de género implícito": "Filtro por sexo y edad sin relacion con la funcion",
    "sesgo de género": "Filtro por sexo y edad sin relacion con la funcion",
    "filtro de edad y género": "Filtro por sexo y edad sin relacion con la funcion",
    "filtro físico": "Filtro por apariencia fisica sin relacion con la funcion",
    "informalidad": "Sin contrato ni ingreso a planilla",
    "informalidad extrema": "Empleador no identificado: sin razon social ni RUC verificable",
    "sin empleador identificable": "Empleador no identificado: sin razon social ni RUC verificable",
    "sin nombre de empleador específico": "Empleador no identificado: sin razon social ni RUC verificable",
    "anonimato del empleador": "Empleador no identificado: sin razon social ni RUC verificable",
    "sin salario especificado": "Remuneracion no especificada en el aviso",
    "sin información salarial": "Remuneracion no especificada en el aviso",
    "salario no especificado": "Remuneracion no especificada en el aviso",
    "salarios asimétricos o irreales": "Remuneracion desproporcionada para el puesto y sin sustento",
    "posible traslado interregional": "Trabajo fuera de la ciudad de residencia",
    "locación periférica o de carretera": "Trabajo fuera de la ciudad de residencia",
    "traslado interregional para aislamiento": "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    "desplazamiento interregional hacia economías ilícitas": "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    "traslado forzado a enclaves mineros": "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    "traslado y desarraigo": "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    "jornada laboral extendida": "Jornada laboral que excede el maximo legal",
    "trabajo doméstico informal": "Trabajo domestico sin contrato ni condiciones definidas",
    "captación de menores de edad": "Convocatoria dirigida a menores de edad",
    "reclutamiento explícito de adolescentes": "Convocatoria dirigida a menores de edad",
    "falsa oferta laboral engañosa": "Oferta laboral sin correspondencia con el trabajo real",
    "falsa oferta de trabajo": "Oferta laboral sin correspondencia con el trabajo real",
    "reclutamiento masivo engañoso": "Oferta laboral sin correspondencia con el trabajo real",
    "entrevistas en recintos privados": "Entrevista en domicilio particular u hotel en lugar de sede de la empresa",
    "coerción para tomar decisiones inmediatas": "Presion de urgencia para impedir verificacion",
    "ausencia de exigencia de experiencia": "Ausencia total de requisitos",
    "ninguna": "Ninguna señal de alerta detectada",
}

SIN_BANDERAS = "- Ninguna señal de alerta detectada"

# ajustes revisados a mano, por id del archivo crudo: (nivel, explicacion)
# id 5: azafata "buena presencia" con razon social, sueldo formal y contrato
#       permanente. La exigencia de apariencia merece señalarse, pero marcarla
#       "alto" entrena al modelo a alarmarse con ofertas formales de restaurante
#       y dispara falsos positivos, que es lo que mata la confianza en la
#       herramienta. Se corrige a "medio" y se reescribe la explicacion: si el
#       nivel baja pero el texto sigue diciendo "grave" y "reporta al 1818", el
#       modelo aprende a contradecir su propia etiqueta.
CORRECCIONES = {
    5: ("medio",
        "El empleador esta identificado, el sueldo es acorde al mercado y el contrato es "
        "permanente, lo que aleja el aviso del perfil de captacion. Aun asi, exigir "
        "\"buena presencia\" es un criterio de seleccion discriminatorio y ajeno a la funcion. "
        "Verifica el RUC en SUNAT y pide que la entrevista sea en la sede de la empresa."),
}


def normalizar_bandera(linea):
    texto = linea.lstrip("- ").strip()
    clave = texto.lower().rstrip(".")
    if clave in CATALOGO:
        return CATALOGO[clave]
    # ya viene del catalogo (primera letra mayuscula, frase larga)
    if len(texto) > 25:
        return texto
    return texto[0].upper() + texto[1:] if texto else texto


def normalizar_respuesta(respuesta, nivel_forzado=None, explicacion_nueva=None):
    lineas = respuesta.split("\n")
    nivel = re.match(r"RIESGO: (\w+)", lineas[0])
    nivel = nivel_forzado or (nivel.group(1) if nivel else "medio")

    banderas, explicacion = [], ""
    for l in lineas[1:]:
        if l.startswith("- "):
            banderas.append(normalizar_bandera(l))
        elif l.startswith("EXPLICACION:"):
            explicacion = l[len("EXPLICACION:"):].strip()
    if explicacion_nueva:
        explicacion = explicacion_nueva

    # sin duplicados, conservando el orden
    vistas, unicas = set(), []
    for b in banderas:
        if b.lower() not in vistas:
            vistas.add(b.lower())
            unicas.append(b)

    if nivel == "bajo" or not unicas:
        cuerpo = SIN_BANDERAS
    else:
        cuerpo = "\n".join("- " + b for b in unicas)
    return "RIESGO: %s\nBANDERAS:\n%s\nEXPLICACION: %s" % (nivel, cuerpo, explicacion)


def main():
    if len(sys.argv) < 3:
        print("Uso: python normalizar_avisos.py <entrada.jsonl> <salida.jsonl>")
        return 1
    entrada, salida = sys.argv[1], sys.argv[2]

    conservados, descartados, corregidos = [], [], []
    for linea in open(entrada, encoding="utf-8"):
        linea = linea.strip()
        if not linea:
            continue
        ej = json.loads(linea)
        ident = ej.get("id")

        if ej.get("tipo") == "ilustrativo":
            descartados.append((ident, ej.get("fuente", "?")))
            continue

        usuario = ej["messages"][0]["content"].strip()
        if not usuario.startswith("Analiza este aviso"):
            usuario = PREFIJO + usuario

        correccion = CORRECCIONES.get(ident)
        nivel_forzado, explicacion_nueva = correccion if correccion else (None, None)
        if nivel_forzado:
            original = re.match(r"RIESGO: (\w+)", ej["messages"][1]["content"])
            corregidos.append((ident, original.group(1) if original else "?", nivel_forzado))

        respuesta = normalizar_respuesta(ej["messages"][1]["content"], nivel_forzado,
                                         explicacion_nueva)
        conservados.append({
            "fuente": ej.get("fuente"),
            "url": ej.get("url"),
            "tipo": ej.get("tipo"),
            "messages": [{"role": "user", "content": usuario},
                         {"role": "assistant", "content": respuesta}],
        })

    with open(salida, "w", encoding="utf-8") as f:
        for ej in conservados:
            f.write(json.dumps(ej, ensure_ascii=False) + "\n")

    conteo = {}
    for ej in conservados:
        n = ej["messages"][1]["content"].split("\n")[0].replace("RIESGO: ", "")
        conteo[n] = conteo.get(n, 0) + 1

    print("%s -> %s" % (entrada, salida))
    print("  conservados : %d" % len(conservados))
    for k in ("alto", "medio", "bajo"):
        print("     %-6s %2d" % (k, conteo.get(k, 0)))
    print("  descartados : %d (tipo 'ilustrativo': no son avisos de trabajo)" % len(descartados))
    for ident, fuente in descartados:
        print("     id %-3s %s" % (ident, fuente))
    if corregidos:
        print("  etiquetas corregidas a mano:")
        for ident, antes, ahora in corregidos:
            print("     id %-3s %s -> %s" % (ident, antes, ahora))
    return 0


if __name__ == "__main__":
    sys.exit(main())
