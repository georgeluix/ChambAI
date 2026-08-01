# -*- coding: utf-8 -*-
"""Reglas deterministas y parser de la respuesta de Gemma."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


BANDERAS_GRAVES = (
    "Filtro por sexo, edad y apariencia fisica sin relacion con la funcion",
    "Solicitud de fotografias de cuerpo entero o medidas corporales",
    "Alojamiento dentro del centro de trabajo",
    "Retencion del documento de identidad",
    "Exigencia de confidencialidad frente al entorno familiar",
    "Servicios de acompañamiento en local privado y horario nocturno",
)

BANDERAS_CRITICAS = (
    "Empleador no identificado: sin razon social ni RUC verificable",
    "Remuneracion desproporcionada para el puesto y sin sustento",
    "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    "Cobro adelantado al postulante",
    "Solicitud de documentos personales antes de cualquier entrevista",
    "Entrevista en domicilio particular u hotel en lugar de sede de la empresa",
    "Contacto unicamente por mensajeria con un numero personal",
    "Presion de urgencia para impedir verificacion",
)

BANDERAS_LEVES = (
    "Remuneracion no especificada en el aviso",
    "Ausencia total de requisitos",
    "Sin contrato ni ingreso a planilla",
    "Trabajo en horario nocturno",
    "Trabajo fuera de la ciudad de residencia",
    "Postulacion por mensajeria personal",
)

BANDERA_MENORES = "Convocatoria dirigida a menores de edad"
BANDERA_SIN_ALERTAS = "Ninguna señal de alerta detectada"

# El corpus historico contiene algunas redacciones anteriores al catalogo
# definitivo. Se traducen aqui para que la API entregue nombres estables.
ALIAS_BANDERAS = {
    "Ausencia total de requisitos para un puesto bien remunerado": (
        "Ausencia total de requisitos",
    ),
    "Ausencia de requisitos de experiencia": ("Ausencia total de requisitos",),
    "Mensaje de urgencia en la convocatoria": (
        "Presion de urgencia para impedir verificacion",
    ),
    "Empresa sin RUC visible en el aviso": (
        "Empleador no identificado: sin razon social ni RUC verificable",
    ),
    "Empleador no identificado: sin razon social ni RUC": (
        "Empleador no identificado: sin razon social ni RUC verificable",
    ),
    "Traslado inmediato fuera de la ciudad con pasajes cubiertos por el empleador": (
        "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    ),
    "Traslado a otra ciudad con pasaje cubierto por el empleador": (
        "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    ),
    "Traslado inmediato a zona de alto riesgo con pasaje cubierto por el empleador": (
        "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    ),
    "Traslado internacional con pasaje y tramites cubiertos por el empleador": (
        "Traslado fuera de la ciudad con pasaje cubierto por el empleador",
    ),
    "Alojamiento en el centro de trabajo con restriccion de salida": (
        "Alojamiento dentro del centro de trabajo",
    ),
    "Permanencia prolongada en el centro de trabajo sin posibilidad de salida": (
        "Alojamiento dentro del centro de trabajo",
    ),
    "Alojamiento en el centro de trabajo con retencion de documentos": (
        "Alojamiento dentro del centro de trabajo",
        "Retencion del documento de identidad",
    ),
    "Alojamiento en el domicilio del empleador bajo modalidad cama adentro": (
        "Alojamiento dentro del centro de trabajo",
    ),
    "Filtro por sexo y edad sin relacion con la funcion": (
        "Filtro por sexo, edad y apariencia fisica sin relacion con la funcion",
    ),
    "Filtro por apariencia fisica sin relacion con la funcion": (
        "Filtro por sexo, edad y apariencia fisica sin relacion con la funcion",
    ),
    "Solicitud de fotografias de cuerpo entero en ropa de baño": (
        "Solicitud de fotografias de cuerpo entero o medidas corporales",
    ),
    "Solicitud de fotografia personal como filtro": (
        "Solicitud de fotografias de cuerpo entero o medidas corporales",
    ),
    "Entrevista en habitacion de hotel en lugar de sede de la empresa": (
        "Entrevista en domicilio particular u hotel en lugar de sede de la empresa",
    ),
    "Solicitud de documentos personales antes de cualquier contrato": (
        "Solicitud de documentos personales antes de cualquier entrevista",
    ),
    "Servicios de acompañamiento en local nocturno": (
        "Servicios de acompañamiento en local privado y horario nocturno",
    ),
    "Trabajo en local privado de acceso restringido": (
        "Servicios de acompañamiento en local privado y horario nocturno",
    ),
    "Exigencia de discrecion sobre la naturaleza del trabajo": (
        "Exigencia de confidencialidad frente al entorno familiar",
    ),
    "Promesa de ingresos elevados sin sustento": (
        "Remuneracion desproporcionada para el puesto y sin sustento",
    ),
    "Postulacion unicamente por mensajeria": ("Postulacion por mensajeria personal",),
    "Postulacion unicamente por mensajeria personal": (
        "Postulacion por mensajeria personal",
    ),
    "Trabajo fuera de la ciudad de residencia con alojamiento provisto": (
        "Trabajo fuera de la ciudad de residencia",
    ),
    "Remuneracion referida a un tarifario no detallado en el aviso": (
        "Remuneracion no especificada en el aviso",
    ),
    "Pago en efectivo sin boleta": ("Sin contrato ni ingreso a planilla",),
    "Empresa en proceso de formalizacion, sin RUC en el aviso": (
        "Empleador no identificado: sin razon social ni RUC verificable",
    ),
    "Trabajo domestico sin contrato ni condiciones definidas": (
        "Sin contrato ni ingreso a planilla",
    ),
    "Trabajo nocturno en local de expendio de alcohol para menores": (
        "Trabajo en horario nocturno",
    ),
    # Estas señales describen problemas laborales, pero no pertenecen al
    # catalogo cerrado de captacion. Se omiten de la respuesta estructurada.
    "Jornada laboral que excede el maximo legal": (),
    "Adelanto de dinero como mecanismo de enganche": (),
    "Remuneracion variable sin sueldo base durante dos meses": (),
    "Correo de contacto no corporativo": (),
}

CATALOGO_POR_GRAVEDAD = {
    "grave": BANDERAS_GRAVES,
    "critica": BANDERAS_CRITICAS,
    "leve": BANDERAS_LEVES,
}

_PATRON_SALIDA = re.compile(
    r"\A\s*RIESGO:\s*(?P<riesgo>bajo|medio|alto)\s*\r?\n"
    r"BANDERAS:\s*\r?\n"
    r"(?P<banderas>(?:[ \t]*-[ \t]*[^\r\n]+(?:\r?\n|$))+?)"
    r"[ \t]*EXPLICACION:\s*(?P<explicacion>.+?)\s*\Z",
    re.IGNORECASE | re.DOTALL,
)

_PATRON_TELEFONO = re.compile(r"(?<!\d)9(?:[\s.\-]*\d){8}(?!\d)")


def normalizar(texto: str) -> str:
    """Pasa a minusculas y elimina tildes para comparar patrones."""
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto.lower())
        if not unicodedata.combining(caracter)
    )


def es_aviso_laboral(texto: str) -> bool:
    """Reconoce un aviso por su texto sin delegar esa decision al modelo visual."""
    limpio = normalizar(texto)
    if limpio.strip().upper() in {"SIN_TEXTO", "SIN_AVISO"}:
        return False

    patrones_directos = (
        r"\b(?:se\s+)?(?:busca|buscamos|necesita|necesitamos|requiere|contrata)\b",
        r"\b(?:estamos|empresa)\s+en\s+busca\b",
        r"\b(?:vacante|vacantes|convocatoria|postula|postulacion)\b",
        r"\b(?:envia|enviar|manda|mandar)\s+(?:tu\s+)?cv\b",
        r"\btrabaja\s+con\s+nosotros\b",
    )
    if any(re.search(patron, limpio) for patron in patrones_directos):
        return True

    grupos_laborales = (
        r"\b(?:sueldo|salario|remuneracion|pago)\b",
        r"\b(?:comision|comisiones|propina|propinas)\b",
        r"\b(?:horario|turno|jornada)\b",
        r"\b(?:requisito|requisitos|experiencia)\b",
        r"\b(?:planilla|beneficios|essalud|cts)\b",
        r"\b(?:empleo|trabajo|puesto|cargo|laboral)\b",
    )
    coincidencias = sum(bool(re.search(patron, limpio)) for patron in grupos_laborales)
    return coincidencias >= 2


def _rango_incluye_menor(texto: str) -> bool:
    patron = re.compile(
        r"(?<![\d:])\b(?:entre\s+|de\s+)?(?P<inicio>\d{1,2})\s*"
        r"(?:a|hasta|-)\s*(?:los\s+)?(?P<fin>\d{1,2})"
        r"(?P<anos>\s*anos)?\b(?![:\d])"
    )
    for coincidencia in patron.finditer(texto):
        tramo = texto[max(0, coincidencia.start() - 22) : coincidencia.end() + 22]
        if re.search(r"\b(?:experiencia|ciclo|sueldo|salario|soles|horario|hora)\b|s/", tramo):
            continue
        inicio = int(coincidencia.group("inicio"))
        fin = int(coincidencia.group("fin"))
        incluye_edad_posible = any(10 <= edad < 18 for edad in (inicio, fin))
        incluye_edad_explicita = bool(coincidencia.group("anos")) and min(inicio, fin) < 18
        if incluye_edad_posible or incluye_edad_explicita:
            return True
    return False


def detectar_menores(texto: str) -> bool:
    """Detecta convocatorias cuyo rango admite postulantes menores de 18."""
    limpio = normalizar(texto)
    frases_directas = (
        "menores de edad",
        "menor de edad",
        "no importa si estudias secundaria",
        "aunque estudies secundaria",
    )
    if any(frase in limpio for frase in frases_directas):
        return True
    if _rango_incluye_menor(limpio):
        return True

    for patron in (
        r"\bdesde\s+(?:los\s+)?(\d{1,2})(\s*anos)?\b",
        r"\bmayores?\s+de\s+(\d{1,2})(?:\s*anos)?\b",
        r"\b(?:edad|edades)\s*(?:de|desde|:)?\s*(\d{1,2})\b",
        r"\b(?:chicas|chicos|jovenes|postulantes|personal)\s+de\s+"
        r"(\d{1,2})\s*anos\b",
    ):
        coincidencia = re.search(patron, limpio)
        if not coincidencia:
            continue
        edad = int(coincidencia.group(1))
        tramo = limpio[coincidencia.start() : coincidencia.end() + 18]
        if "desde" in coincidencia.group(0) and re.search(r"\b(?:ciclo|experiencia)\b", tramo):
            continue
        if "mayor" in coincidencia.group(0):
            if edad < 17:
                return True
        elif "edad" in coincidencia.group(0) and edad < 18:
            return True
        elif edad < 18 and (edad >= 10 or "anos" in coincidencia.group(0)):
            return True
    return False


def detectar_cobro_postulante(texto: str) -> bool:
    """Detecta pedidos de dinero ligados al proceso de postulacion."""
    limpio = normalizar(texto)
    patrones = (
        r"\b(?:deposita|depositar|deposite|yapea|yapear|transfiere|transferir)\b",
        r"\b(?:debes|debera[sn]?|tienes que|se requiere)\s+"
        r"(?:pagar|abonar|depositar|transferir)\b",
        r"\b(?:pago|cobro|cuota|abono|deposito)\s+(?:de|por|para)\s+"
        r"(?:garantia|examen medico|uniforme|tramite|inscripcion|carnet|capacitacion)\b",
        r"\b(?:garantia|examen medico|uniforme|tramite|inscripcion|carnet)\b"
        r".{0,35}\b(?:s/?\.?\s*\d+|\d+\s*soles)\b",
        r"\b(?:s/?\.?\s*\d+|\d+\s*soles)\b.{0,35}\bse te devuelve\b",
    )
    return any(re.search(patron, limpio) for patron in patrones)


def telefonos_peruanos_enmascarados(texto: str) -> list[str]:
    """Devuelve telefonos hallados sin exponer sus ultimos seis digitos."""
    telefonos: list[str] = []
    for coincidencia in _PATRON_TELEFONO.finditer(texto):
        digitos = re.sub(r"\D", "", coincidencia.group(0))
        enmascarado = f"{digitos[:3]}******"
        if enmascarado not in telefonos:
            telefonos.append(enmascarado)
    return telefonos


def contacto_solo_mensajeria(texto: str) -> bool:
    """Marca mensajeria personal cuando no existe otro canal verificable."""
    limpio = normalizar(texto)
    tiene_telefono = bool(_PATRON_TELEFONO.search(texto))
    menciona_mensajeria = bool(
        re.search(
            r"\b(?:whatsapp|wsp|wasap|mensajeria|inbox|dm)\b|"
            r"\bescrib(?:e|eme|ir|an)\s+(?:unicamente\s+)?(?:al\s+)?"
            r"(?:privado|numero)?\b",
            limpio,
        )
    )
    canal_alternativo = bool(
        re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", limpio)
        or re.search(
            r"\b(?:portal|pagina web|sitio web|linkedin|correo|email|e-mail|"
            r"oficina|sede|direccion|avenida|jiron|calle|local ubicado|"
            r"presentar cv|llamar)\b|\b(?:av|jr)\.",
            limpio,
        )
    )
    return tiene_telefono and menciona_mensajeria and not canal_alternativo


def aplicar_reglas(texto: str) -> dict[str, Any]:
    """Ejecuta todas las reglas antes de consultar al modelo."""
    banderas: list[dict[str, str]] = []
    riesgo_forzado: str | None = None

    if detectar_menores(texto):
        banderas.append(
            {"texto": BANDERA_MENORES, "gravedad": "grave", "origen": "regla"}
        )
        riesgo_forzado = "alto"

    if detectar_cobro_postulante(texto):
        banderas.append(
            {
                "texto": "Cobro adelantado al postulante",
                "gravedad": "critica",
                "origen": "regla",
            }
        )
        riesgo_forzado = "alto"

    solo_mensajeria = contacto_solo_mensajeria(texto)
    if solo_mensajeria:
        banderas.append(
            {
                "texto": "Contacto unicamente por mensajeria con un numero personal",
                "gravedad": "critica",
                "origen": "regla",
            }
        )

    return {
        "banderas": banderas,
        "riesgo_forzado": riesgo_forzado,
        "telefonos_enmascarados": telefonos_peruanos_enmascarados(texto),
        "contacto_solo_mensajeria": solo_mensajeria,
    }


def parsear_salida_modelo(texto: str) -> dict[str, Any]:
    """Convierte el formato entrenado a una estructura segura para la API."""
    coincidencia = _PATRON_SALIDA.fullmatch(texto)
    if not coincidencia:
        return {
            "formato_valido": False,
            "texto_crudo": texto,
            "riesgo": None,
            "banderas": [],
            "explicacion": "",
        }

    banderas = [
        linea.strip()[1:].strip()
        for linea in coincidencia.group("banderas").splitlines()
        if linea.strip().startswith("-")
    ]
    return {
        "formato_valido": True,
        "riesgo": coincidencia.group("riesgo").lower(),
        "banderas": banderas,
        "explicacion": coincidencia.group("explicacion").strip(),
    }


def canonizar_bandera(texto: str) -> tuple[str, ...]:
    """Convierte variantes conocidas y descarta etiquetas fuera del catalogo."""
    objetivo = normalizar(texto)
    for alias, banderas in ALIAS_BANDERAS.items():
        if objetivo == normalizar(alias):
            return banderas
    for banderas in CATALOGO_POR_GRAVEDAD.values():
        for bandera in banderas:
            if objetivo == normalizar(bandera):
                return (bandera,)
    if objetivo == normalizar(BANDERA_MENORES):
        return (BANDERA_MENORES,)
    # El modelo no puede ampliar el contrato por su cuenta: una frase inventada
    # no debe convertirse en una señal visible ni sumar puntaje.
    return ()


def gravedad_de_bandera(texto: str) -> str:
    """Clasifica una bandera; tolera pequenas variaciones del modelo."""
    objetivo = normalizar(texto)
    if objetivo == normalizar(BANDERA_MENORES):
        return "grave"
    for gravedad, banderas in CATALOGO_POR_GRAVEDAD.items():
        if any(objetivo == normalizar(bandera) for bandera in banderas):
            return gravedad

    claves_graves = (
        "retencion",
        "cuerpo entero",
        "medidas corporales",
        "alojamiento dentro",
        "confidencialidad",
        "acompanamiento",
    )
    claves_criticas = (
        "empleador no identificado",
        "remuneracion desproporcionada",
        "traslado",
        "pasaje",
        "cobro",
        "documentos personales",
        "hotel",
        "mensajeria",
        "urgencia",
    )
    if any(clave in objetivo for clave in claves_graves):
        return "grave"
    if any(clave in objetivo for clave in claves_criticas):
        return "critica"
    return "leve"


def calcular_puntaje(banderas: list[dict[str, str]]) -> int:
    pesos = {"grave": 30, "critica": 20, "leve": 8}
    return min(100, sum(pesos[bandera["gravedad"]] for bandera in banderas))


if __name__ == "__main__":
    casos = (
        ("Buscamos chicas desde los 16 para bar", True, False),
        ("Se requiere de 18 a 25 anos", False, False),
        ("Deposita S/ 200 para el uniforme", False, True),
        ("Se paga S/ 1800 en planilla", False, False),
    )
    for aviso, espera_menor, espera_cobro in casos:
        assert detectar_menores(aviso) is espera_menor
        assert detectar_cobro_postulante(aviso) is espera_cobro

    muestra = (
        "RIESGO: medio\nBANDERAS:\n- Trabajo en horario nocturno\n"
        "EXPLICACION: Conviene verificar las condiciones."
    )
    assert parsear_salida_modelo(muestra)["formato_valido"]
    print("Extractor: pruebas basicas correctas.")
