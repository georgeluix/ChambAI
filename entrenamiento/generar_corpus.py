# -*- coding: utf-8 -*-
"""Genera corpus.jsonl para el fine-tune de Chamba Segura.

Ensambla avisos de empleo por slots (empresa, sueldo, requisitos, condiciones,
contacto, urgencia). Cada slot aporta banderas de riesgo; la etiqueta se DERIVA
de las banderas inyectadas, no al reves. Eso garantiza consistencia perfecta
entre el aviso y su respuesta, que es lo unico que el modelo puede aprender.

Uso: python generar_corpus.py
"""
import json
import os
import random
import re
import unicodedata

random.seed(20260801)

PREFIJO = "Analiza este aviso de empleo:\n\n"

# --- pesos derivados del dataset de denuncias PNP 2017-2023 -----------------
# Los patrones no se eligen al azar: su frecuencia en el corpus reproduce la
# frecuencia con que aparecen en 3 822 denuncias reales. Si el 60.2% de los
# casos usan engaño y solo el 6.8% amenaza, el corpus debe reflejarlo; de lo
# contrario el modelo se calibra para alarmarse por lo infrecuente.
_AQUI = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_AQUI, "..", "datos", "datos_trata.json"), encoding="utf-8") as _f:
    TRATA = json.load(_f)

_NAC = TRATA["nacional"]


def _pesos(clave):
    """{subcategoria: pct} de una categoria del dataset."""
    return {k: v["pct"] for k, v in _NAC[clave]["distribucion"].items()}


def elegir(opciones):
    """opciones: dict {valor: peso}. Devuelve un valor segun su peso real."""
    claves = list(opciones)
    return random.choices(claves, weights=[opciones[k] for k in claves])[0]


# Ciudades de origen ponderadas por denuncias del departamento
_DEPTO_CIUDAD = {
    "LIMA": "Lima", "LAMBAYEQUE": "Chiclayo", "CUSCO": "Cusco", "AREQUIPA": "Arequipa",
    "AYACUCHO": "Ayacucho", "PUNO": "Juliaca", "HUÁNUCO": "Huanuco", "LORETO": "Iquitos",
    "SAN MARTÍN": "Tarapoto", "MADRE DE DIOS": "Puerto Maldonado", "JUNÍN": "Huancayo",
    "TACNA": "Tacna", "CAJAMARCA": "Cajamarca", "TUMBES": "Tumbes", "PIURA": "Piura",
    "LA LIBERTAD": "Trujillo", "ICA": "Ica", "ÁNCASH": "Chimbote", "UCAYALI": "Pucallpa",
    "CALLAO": "Callao",
}
CIUDADES_PESO = {c: TRATA["departamentos"][d]["denuncias"]
                 for d, c in _DEPTO_CIUDAD.items() if d in TRATA["departamentos"]}
CIUDADES = list(CIUDADES_PESO)

# Destinos de traslado: ponderados por cuantas denuncias del departamento
# entraron por oferta de trabajo (Madre de Dios encabeza con 91.3%)
_DESTINO_NOMBRE = {
    "MADRE DE DIOS": "La Pampa (Madre de Dios)", "LORETO": "Iquitos",
    "CUSCO": "la selva de Cusco", "PUNO": "la frontera con Bolivia",
    "UCAYALI": "Pucallpa", "SAN MARTÍN": "Tarapoto", "AREQUIPA": "Chala (Arequipa)",
    "TACNA": "Tacna", "HUÁNUCO": "Tingo Maria", "TUMBES": "la frontera con Ecuador",
}
DESTINOS_PESO = {n: TRATA["departamentos"][d]["por_oferta_de_trabajo"]
                 for d, n in _DESTINO_NOMBRE.items() if d in TRATA["departamentos"]}


def destino():
    return elegir(DESTINOS_PESO)

NOMBRES_CONTACTO = ["Karla", "Señora Rosa", "Jhon", "Miss Yanet", "el Sr. Vega",
                    "Milagros", "Cesar", "la Srta. Paola", "Dany", "el encargado"]

EMPRESAS = ["Corporacion Andina de Servicios", "Textiles del Norte", "Grupo Vitalis",
            "Distribuidora Sol Naciente", "Constructora Marcahuasi", "Alimentos Piura",
            "Servicios Logisticos Pacifico", "Clinica San Marcos", "Retail Peru Plus",
            "Agroindustrial Chavimochic", "Contact Center Lima Norte", "Ferreteria El Roble",
            "Transportes Huascaran", "Consultora Delta", "Supermercados Mi Barrio",
            "Laboratorios Quimtec", "Seguridad Integral Andes", "Editorial Amauta"]

PUESTOS_FORMALES = [
    ("asistente administrativo", ["manejo de Excel intermedio", "estudios tecnicos concluidos"]),
    ("operario de produccion", ["secundaria completa", "disponibilidad para turnos rotativos"]),
    ("asesor de ventas", ["experiencia minima de 6 meses en ventas", "secundaria completa"]),
    ("teleoperador de call center", ["buena dicción", "manejo basico de computo"]),
    ("almacenero", ["experiencia en inventarios", "disponibilidad inmediata"]),
    ("auxiliar contable", ["egresado de contabilidad", "manejo de Concar"]),
    ("chofer de reparto", ["licencia A-IIB vigente", "certificado de antecedentes penales"]),
    ("recepcionista", ["experiencia en atencion al cliente", "estudios tecnicos en administracion"]),
    ("tecnico de mantenimiento", ["formacion tecnica en electricidad", "3 años de experiencia"]),
    ("promotor de campo", ["secundaria completa", "disponibilidad para viajar dentro de la region"]),
    ("cajero", ["experiencia en manejo de efectivo", "secundaria completa"]),
    ("auxiliar de enfermeria", ["titulo tecnico habilitado", "colegiatura vigente"]),
    ("digitador", ["velocidad de tipeo de 40 ppm", "manejo de Google Sheets"]),
    ("supervisor de limpieza", ["experiencia liderando equipos", "secundaria completa"]),
    ("ayudante de cocina", ["carnet de sanidad vigente", "experiencia en cocina industrial"]),
]

# Puestos gancho ponderados por el LUGAR DE EXPLOTACION real de las denuncias:
# night club 267, prostibulo 207, servicio domestico 86, discoteca 28,
# mercados 16, mineria artesanal 13, agropecuaria 10, masajes 9, modelaje 5.
_PUESTOS_POR_LUGAR = {
    "night club": ["anfitrionas para night club", "damas de compañia para night club",
                   "chicas para bar karaoke", "señoritas para atencion en restobar"],
    "prostibulo": ["damas de compañia", "acompañantes para clientes ejecutivos",
                   "personal para atencion en reservados"],
    "servicio domestico": ["personal domestico cama adentro", "empleada del hogar cama adentro",
                           "cocinera para casa de familia con alojamiento"],
    "discoteca": ["personal de imagen para discoteca", "azafatas para eventos nocturnos"],
    "trabajo en mercados": ["ayudantes para puesto de mercado", "personal para tienda mayorista"],
    "mineria artesanal": ["personal para campamento minero", "cocineras para campamento minero"],
    "actividad agropecuaria": ["peones para fundo agricola", "personal para cosecha"],
    "centro de masajes": ["personal para spa", "masajistas sin experiencia"],
    "estudio de modelaje": ["modelos para catalogo", "modelos para sesion fotografica"],
    "actividad pesquera": ["tripulantes para embarcacion pesquera"],
}
_PESO_LUGAR = _pesos("lugar_explotacion")
PUESTOS_GANCHO_PESO = {lugar: _PESO_LUGAR.get(lugar, 0.5)
                       for lugar in _PUESTOS_POR_LUGAR}


def puesto_gancho():
    return random.choice(_PUESTOS_POR_LUGAR[elegir(PUESTOS_GANCHO_PESO)])


# Condiciones ponderadas por el MEDIO EMPLEADO POR EL TRATANTE en las denuncias.
# El engaño (60.2%) no es una condicion en si: se materializa en el traslado, el
# local nocturno, el secreto y la entrevista irregular, asi que se reparte.
_MEDIO = _pesos("medio")
_ENGANO = _MEDIO.get("engaño", 60.0)
PESO_CONDICION = {
    "viaje_inmediato": _ENGANO * 0.35,
    "nocturno_privado": _ENGANO * 0.30,
    "secreto": _ENGANO * 0.20,
    "entrevista_rara": _ENGANO * 0.15,
    "cobro": _MEDIO.get("concesion o recepcion de pagos", 9.9),
    "encierro": _MEDIO.get("privacion de la libertad", 2.5),
    "documentos": _MEDIO.get("fraude", 0.9) + _MEDIO.get("abuso de poder", 0.8),
}

RUBROS_VAGOS = ["Empresa del rubro entretenimiento", "Importante empresa",
                "Grupo empresarial en expansion", "Empresa de servicios",
                "Reconocida corporacion", "Negocio familiar", "Empresa privada"]

# ---------------------------------------------------------------------------
# Banderas. (texto_en_el_aviso, etiqueta_para_la_respuesta, peso)
# peso: "extrema" = por si sola clasifica alto; "critica" = dos hacen alto;
#       "leve" = empuja a medio.
# ---------------------------------------------------------------------------

def _tel():
    # Marcador deliberadamente no enrutable: el corpus nunca debe inventar un
    # numero que pueda pertenecer a una persona real.
    return "9XX XXX XXX"

def _ruc():
    # Conserva el formato visual del aviso sin fabricar un RUC valido.
    return "20XXXXXXXXX"


SLOT_EMPRESA = {
    "limpio": [
        lambda: ("{emp} S.A.C. (RUC %s) requiere" % _ruc(), None, None),
        lambda: ("{emp}, empresa formal con 12 años en el mercado, convoca a", None, None),
        lambda: ("{emp} E.I.R.L. (RUC %s) esta contratando" % _ruc(), None, None),
    ],
    "anonimo": [
        lambda: (random.choice(RUBROS_VAGOS) + " necesita",
                 "Empleador no identificado: sin razon social ni RUC verificable", "critica"),
        lambda: ("Con urgencia se necesita",
                 "Empleador no identificado: sin razon social ni RUC verificable", "critica"),
        lambda: ("Buscamos", "Empleador no identificado: sin razon social ni RUC verificable", "critica"),
    ],
    "semi": [
        lambda: ("{emp} (en proceso de formalizacion) busca",
                 "Empleador no identificado: sin razon social ni RUC verificable", "critica"),
        lambda: ("{emp} solicita", None, None),
    ],
}

SLOT_SUELDO = {
    "limpio": [
        lambda: ("Sueldo S/ %s mensuales en planilla, mas beneficios de ley." % random.choice([1130, 1250, 1400, 1500, 1650, 1800, 2000, 2200]), None, None),
        lambda: ("Remuneracion S/ %s mas movilidad y asignacion familiar." % random.choice([1300, 1450, 1600, 1900]), None, None),
        lambda: ("Banda salarial de S/ %s a S/ %s segun experiencia, en planilla." % random.choice([(1200, 1600), (1500, 2100), (1800, 2500)]), None, None),
    ],
    "irreal": [
        lambda: ("Pago de S/ %s SEMANALES garantizados." % random.choice([1500, 2000, 2500, 3000]),
                 "Remuneracion desproporcionada para el puesto y sin sustento", "critica"),
        lambda: ("Ganaras entre S/ %s y S/ %s al mes desde el primer dia, sin experiencia." % random.choice([(5000, 8000), (6000, 10000), (4500, 7000)]),
                 "Remuneracion desproporcionada para el puesto y sin sustento", "critica"),
        lambda: ("Ingresos de USD %s mensuales libres, mas propinas." % random.choice([1500, 2000, 2500]),
                 "Remuneracion desproporcionada para el puesto y sin sustento", "critica"),
        lambda: ("Pago diario de S/ %s en efectivo." % random.choice([250, 300, 400, 500]),
                 "Remuneracion desproporcionada para el puesto y sin sustento", "critica"),
    ],
    "vago": [
        lambda: ("Excelentes ingresos, sueldo a tratar en la entrevista.",
                 "Remuneracion no especificada en el aviso", "leve"),
        lambda: ("Ingresos segun desempeño, sin tope.",
                 "Remuneracion no especificada en el aviso", "leve"),
        lambda: ("Sueldo acorde al mercado (se conversa).",
                 "Remuneracion no especificada en el aviso", "leve"),
    ],
}

SLOT_REQUISITOS = {
    "limpio": [
        lambda: ("Requisitos: {req1}, {req2}. Enviar CV documentado.", None, None),
        lambda: ("Perfil: {req1} y {req2}.", None, None),
        lambda: ("Se requiere {req1}; deseable {req2}.", None, None),
    ],
    "perfil_fisico": [
        lambda: ("Solo señoritas de 18 a 25 años, buena presencia y contextura delgada.",
                 "Filtro por sexo, edad y apariencia fisica sin relacion con la funcion", "extrema"),
        lambda: ("Requisito: chicas de excelente presencia, estatura minima 1.65.",
                 "Filtro por sexo, edad y apariencia fisica sin relacion con la funcion", "extrema"),
        lambda: ("Buscamos personal femenino joven, sin tatuajes visibles, muy buena presencia.",
                 "Filtro por sexo, edad y apariencia fisica sin relacion con la funcion", "extrema"),
    ],
    "fotos": [
        lambda: ("Enviar 3 fotos de cuerpo entero recientes y tus medidas al WhatsApp.",
                 "Solicitud de fotografias de cuerpo entero o medidas corporales", "extrema"),
        lambda: ("Adjuntar fotos actuales de cuerpo completo (indispensable para el casting).",
                 "Solicitud de fotografias de cuerpo entero o medidas corporales", "extrema"),
    ],
    # La convocatoria a menores NO se entrena por ejemplos de texto: se resuelve
    # con una regla determinista en el extractor (ver extractor.py). Una linea
    # legal tan dura no debe depender de que el modelo haya visto el patron; un
    # regex sobre edades menores de 18 es mas confiable que el fine-tuning, y
    # evita que el corpus necesite ejemplos de ese tipo.
    "sin_nada": [
        lambda: ("No se requiere experiencia ni estudios, solo ganas de trabajar.",
                 "Ausencia total de requisitos", "leve"),
        lambda: ("Sin experiencia. Nosotros te capacitamos en 2 dias.",
                 "Ausencia total de requisitos", "leve"),
        lambda: ("No pedimos CV ni antecedentes.",
                 "Ausencia total de requisitos", "leve"),
    ],
}

SLOT_CONDICIONES = {
    "limpio": [
        lambda: ("Contrato en planilla desde el primer dia, horario de lunes a viernes de 9:00 a 18:00.", None, None),
        lambda: ("Ingreso a planilla con EsSalud, gratificaciones y CTS. Turno diurno.", None, None),
        lambda: ("Jornada de 48 horas semanales, un dia de descanso, todos los beneficios de ley.", None, None),
        lambda: ("Trabajo presencial en nuestra sede de {ciudad}, contrato a plazo fijo renovable.", None, None),
    ],
    "viaje_inmediato": [
        lambda: ("Viaje INMEDIATO a %s, la empresa cubre pasaje y estadia." % destino(),
                 "Traslado fuera de la ciudad con pasaje cubierto por el empleador", "critica"),
        lambda: ("Se viaja este fin de semana a %s. No te preocupes por el pasaje, nosotros lo pagamos." % destino(),
                 "Traslado fuera de la ciudad con pasaje cubierto por el empleador", "critica"),
        lambda: ("Trabajo en %s. Salida en 48 horas, pasaje adelantado por la empresa." % destino(),
                 "Traslado fuera de la ciudad con pasaje cubierto por el empleador", "critica"),
    ],
    "encierro": [
        lambda: ("Alojamiento y alimentacion incluidos dentro del local. No se puede salir durante el turno.",
                 "Alojamiento dentro del centro de trabajo", "extrema"),
        lambda: ("Vivienda cama adentro, entregas tu DNI al ingresar por seguridad.",
                 "Retencion del documento de identidad", "extrema"),
        lambda: ("Te quedas en el campamento 30 dias seguidos, sin salidas.",
                 "Alojamiento dentro del centro de trabajo", "extrema"),
    ],
    "cobro": [
        lambda: ("Deposita S/ %s para el examen medico y el uniforme antes de empezar." % random.choice([80, 120, 150, 200, 250]),
                 "Cobro adelantado al postulante", "critica"),
        lambda: ("Se solicita un pago unico de S/ %s por tramite de carnet." % random.choice([100, 180, 300]),
                 "Cobro adelantado al postulante", "critica"),
        lambda: ("Costo de induccion S/ %s, se devuelve con el primer sueldo." % random.choice([150, 200]),
                 "Cobro adelantado al postulante", "critica"),
    ],
    "documentos": [
        lambda: ("Enviar foto de DNI por ambos lados antes de la entrevista.",
                 "Solicitud de documentos personales antes de cualquier entrevista", "critica"),
        lambda: ("Manda tu DNI y una foto tuya para reservar tu cupo.",
                 "Solicitud de documentos personales antes de cualquier entrevista", "critica"),
    ],
    "secreto": [
        lambda: ("Trabajo discreto, no comentar con familiares ni amistades.",
                 "Exigencia de confidencialidad frente al entorno familiar", "extrema"),
        lambda: ("Total discrecion. Lo que pasa aqui no se cuenta afuera.",
                 "Exigencia de confidencialidad frente al entorno familiar", "extrema"),
    ],
    "nocturno_privado": [
        lambda: ("Horario nocturno en local privado, atencion personalizada a clientes VIP.",
                 "Servicios de acompañamiento en local privado y horario nocturno", "extrema"),
        lambda: ("Turno de 9 pm a 4 am, atencion en reservados. Se paga extra por hora adicional.",
                 "Servicios de acompañamiento en local privado y horario nocturno", "extrema"),
    ],
    "entrevista_rara": [
        lambda: ("La entrevista es en un hotel del centro, te paso la habitacion por interno.",
                 "Entrevista en domicilio particular u hotel en lugar de sede de la empresa", "critica"),
        lambda: ("Te entrevistamos en el departamento del jefe, es mas comodo.",
                 "Entrevista en domicilio particular u hotel en lugar de sede de la empresa", "critica"),
    ],
    "informal": [
        lambda: ("Pago semanal en efectivo, sin contrato por ahora.",
                 "Sin contrato ni ingreso a planilla", "leve"),
        lambda: ("Se trabaja por recibo por honorarios.",
                 "Sin contrato ni ingreso a planilla", "leve"),
    ],
    "nocturno_formal": [
        lambda: ("Turno noche de 22:00 a 06:00, con movilidad de retorno y bono nocturno de ley.",
                 "Trabajo en horario nocturno", "leve"),
        lambda: ("Horario rotativo que incluye turnos de madrugada.",
                 "Trabajo en horario nocturno", "leve"),
    ],
    "provincia_formal": [
        lambda: ("El puesto es en nuestra planta de {ciudad2}; se cubre alojamiento en campamento con regimen 14x7 registrado.",
                 "Trabajo fuera de la ciudad de residencia", "leve"),
        lambda: ("Requiere reubicacion a {ciudad2}. Se firma contrato antes del traslado.",
                 "Trabajo fuera de la ciudad de residencia", "leve"),
    ],
}

SLOT_CONTACTO = {
    "limpio": [
        lambda: ("Postula en nuestra bolsa de trabajo o envia tu CV a seleccion@{slug}.invalid", None, None),
        lambda: ("Enviar CV a rrhh@{slug}.invalid indicando el puesto en el asunto.", None, None),
        lambda: ("Postulaciones unicamente por nuestro portal web institucional.", None, None),
    ],
    "anonimo": [
        lambda: ("Solo por WhatsApp al %s, preguntar por %s. No llamar." % (_tel(), random.choice(NOMBRES_CONTACTO)),
                 "Contacto unicamente por mensajeria con un numero personal", "critica"),
        lambda: ("Escribeme al Telegram, el numero es %s. No respondo llamadas." % _tel(),
                 "Contacto unicamente por mensajeria con un numero personal", "critica"),
        lambda: ("Interesadas escribir al %s. Nada de llamadas, solo texto." % _tel(),
                 "Contacto unicamente por mensajeria con un numero personal", "critica"),
    ],
    "mixto": [
        lambda: ("Escribir al WhatsApp %s o al correo de la empresa." % _tel(),
                 "Postulacion por mensajeria personal", "leve"),
        lambda: ("Coordinar por WhatsApp %s con el area de RRHH." % _tel(),
                 "Postulacion por mensajeria personal", "leve"),
    ],
}

SLOT_URGENCIA = {
    "limpio": [lambda: ("", None, None)],
    "extrema": [
        lambda: ("ULTIMAS 2 VACANTES, empiezas HOY MISMO.",
                 "Presion de urgencia para impedir verificacion", "critica"),
        lambda: ("Cupos limitados, decide ahora o pierdes la oportunidad.",
                 "Presion de urgencia para impedir verificacion", "critica"),
    ],
    "leve": [
        lambda: ("Vacantes limitadas.", "Presion de urgencia para impedir verificacion", "critica"),
        lambda: ("Incorporacion inmediata.", None, None),
    ],
}

EXPL_ALTO = [
    "El aviso concentra {n} señales tipicas de captacion con fines de trata: destaca {b1} junto con {b2}. Esta combinacion no corresponde a un proceso de seleccion formal. No respondas ni entregues datos personales y reporta el aviso a la Linea 1818.",
    "Se identifican {n} indicadores de riesgo, entre ellos {b1} y {b2}. El patron coincide con el usado en falsas ofertas de empleo para captar victimas. Evita todo contacto y denuncia al 1818 (Linea contra la Trata).",
    "La oferta reune {n} señales de alerta; las mas graves son {b1} y {b2}. Ningun empleador formal opera de esta forma. No envies documentos ni acudas a la cita; reporta a la Linea 1818.",
    "Riesgo alto por {n} banderas simultaneas, en particular {b1} y {b2}. Es un esquema de enganche laboral. Corta el contacto, guarda capturas del aviso y denuncialo a la Linea 1818.",
]

EXPL_MEDIO = [
    "No se detectan señales criticas de trata, pero {b1} impide verificar al empleador. Antes de continuar exige razon social, RUC, direccion fisica y contrato por escrito.",
    "El aviso es ambiguo: {b1}. No hay indicadores de explotacion, aunque la informacion es insuficiente para confirmar que la oferta es formal. Verifica el RUC en SUNAT y pide que la entrevista sea en la sede de la empresa.",
    "Riesgo intermedio. La señal principal es {b1}, que por si sola no indica trata pero si informalidad. Solicita contrato antes de aceptar y confirma la existencia de la empresa.",
    "Hay elementos que requieren verificacion, sobre todo {b1}. La oferta puede ser legitima, pero no acudas sola a la entrevista ni entregues documentos originales hasta confirmar al empleador.",
]

EXPL_BAJO = [
    "El aviso identifica a la empresa, detalla funciones y requisitos verificables, y ofrece condiciones dentro del marco laboral peruano. No se observan señales de captacion.",
    "La oferta es coherente: empleador identificable, remuneracion acorde al puesto, requisitos proporcionales y canal de postulacion institucional. No hay indicadores de trata.",
    "Convocatoria con estructura formal: razon social, contrato en planilla y proceso de seleccion documentado. Nada en el texto sugiere riesgo de explotacion.",
    "El anuncio cumple los elementos de una oferta legitima: empresa verificable, condiciones laborales explicitas y postulacion por canal institucional. Riesgo bajo.",
]


def _slug(nombre):
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())[:14]


def _elegir(slot, clave):
    return random.choice(slot[clave])()


def construir(objetivo):
    """Devuelve (texto_aviso, nivel, banderas) para el nivel pedido."""
    empresa = random.choice(EMPRESAS)
    ciudad = random.choice(CIUDADES)
    ciudad2 = random.choice([c for c in CIUDADES if c != ciudad])
    puesto, reqs = random.choice(PUESTOS_FORMALES)

    if objetivo == "alto":
        # La condicion se elige segun el MEDIO EMPLEADO POR EL TRATANTE en las
        # denuncias reales: engaño 60.2%, concesion de pagos 9.9%, amenaza 6.8%,
        # privacion de libertad 2.5%, fraude 0.9%. Sin esta ponderacion el
        # modelo se calibra para alarmarse por lo infrecuente.
        cond_key = elegir(PESO_CONDICION)
        req_key = random.choice(["perfil_fisico", "fotos", "sin_nada", "sin_nada"])
        emp_key = random.choice(["anonimo", "anonimo", "semi"])
        suel_key = random.choice(["irreal", "irreal", "vago"])
        cont_key = random.choice(["anonimo", "anonimo", "mixto"])
        urg_key = random.choice(["extrema", "leve", "limpio"])
        if req_key in ("perfil_fisico", "fotos") or cond_key in ("nocturno_privado", "encierro"):
            puesto = puesto_gancho()
    elif objetivo == "medio":
        cond_key = random.choice(["informal", "nocturno_formal", "provincia_formal", "limpio"])
        req_key = random.choice(["sin_nada", "limpio", "limpio"])
        emp_key = random.choice(["semi", "limpio"])
        suel_key = random.choice(["vago", "limpio"])
        cont_key = random.choice(["mixto", "limpio"])
        urg_key = random.choice(["leve", "limpio"])
    else:
        cond_key = req_key = suel_key = cont_key = urg_key = "limpio"
        emp_key = "limpio"

    piezas, banderas, pesos = [], [], []

    for slot, clave in ((SLOT_EMPRESA, emp_key), (SLOT_SUELDO, suel_key),
                        (SLOT_REQUISITOS, req_key), (SLOT_CONDICIONES, cond_key),
                        (SLOT_URGENCIA, urg_key), (SLOT_CONTACTO, cont_key)):
        txt, bandera, peso = _elegir(slot, clave)
        if txt:
            piezas.append(txt)
        if bandera and bandera not in banderas:
            banderas.append(bandera)
            pesos.append(peso)

    cuerpo = " ".join(piezas)
    cuerpo = (cuerpo
              .replace("{emp}", empresa)
              .replace("{ciudad2}", ciudad2)
              .replace("{ciudad}", ciudad)
              .replace("{slug}", _slug(empresa))
              .replace("{req1}", reqs[0])
              .replace("{req2}", reqs[1]))

    # el puesto se inserta despues del verbo de la primera pieza (con punto de cierre)
    inserto = puesto + "."
    aviso = cuerpo.replace("requiere", "requiere " + inserto, 1) if "requiere" in cuerpo else cuerpo
    for verbo in ("convoca a", "esta contratando", "necesita", "Buscamos", "solicita", "busca"):
        if verbo in aviso and puesto not in aviso:
            aviso = aviso.replace(verbo, verbo + " " + inserto, 1)
            break
    if puesto not in aviso:
        aviso = "Se busca " + inserto + " " + aviso

    aviso = re.sub(r"\s+", " ", aviso).strip()
    aviso = "Se busca " + puesto + " en " + ciudad + ". " + aviso if len(aviso) < 90 else aviso

    n_extremas = pesos.count("extrema")
    n_criticas = pesos.count("critica")
    if n_extremas >= 1 or n_criticas >= 2:
        nivel = "alto"
    elif n_criticas == 1 or banderas:
        nivel = "medio"
    else:
        nivel = "bajo"

    return aviso, nivel, banderas, pesos


ORDEN_PESO = {"extrema": 0, "critica": 1, "leve": 2}


def respuesta(nivel, banderas, pesos):
    if nivel == "bajo":
        lineas = ["- Ninguna señal de alerta detectada"]
        expl = random.choice(EXPL_BAJO)
    else:
        lineas = ["- " + b for b in banderas]
        # en la explicacion se citan las banderas mas graves, no las primeras del aviso
        graves = [b for b, _ in sorted(zip(banderas, pesos), key=lambda x: ORDEN_PESO[x[1]])]
        minus = lambda b: b[0].lower() + b[1:]
        if nivel == "alto":
            b2 = minus(graves[1]) if len(graves) > 1 else "la ausencia de un empleador verificable"
            expl = random.choice(EXPL_ALTO).format(n=len(banderas), b1=minus(graves[0]), b2=b2)
        else:
            expl = random.choice(EXPL_MEDIO).format(b1=minus(graves[0]))
    return "RIESGO: %s\nBANDERAS:\n%s\nEXPLICACION: %s" % (nivel, "\n".join(lineas), expl)


def normaliza(t):
    return re.sub(r"\s+", " ", t.strip().lower())


def generar(objetivos):
    """objetivos: dict nivel -> cantidad."""
    salida, vistos = [], set()
    for nivel_pedido, cantidad in objetivos.items():
        logrados, intentos = 0, 0
        while logrados < cantidad and intentos < cantidad * 200:
            intentos += 1
            aviso, nivel, banderas, pesos = construir(nivel_pedido)
            if nivel != nivel_pedido:
                continue
            clave = normaliza(PREFIJO + aviso)[:100]
            if clave in vistos:
                continue
            vistos.add(clave)
            salida.append({
                "origen": "sintetico-propio",
                "tipo": "sintetico",
                "fuente": "Generador local reproducible generar_corpus.py",
                "messages": [
                {"role": "user", "content": PREFIJO + aviso},
                {"role": "assistant", "content": respuesta(nivel, banderas, pesos)},
            ]})
            logrados += 1
        if logrados < cantidad:
            raise SystemExit("Solo se generaron %d/%d de nivel %s" % (logrados, cantidad, nivel_pedido))
    random.shuffle(salida)
    return salida


if __name__ == "__main__":
    # Cantidades calculadas para que, al mezclar con los avisos reales (2/8/15)
    # y los sinteticos externos (9/2/4), el corpus final quede en 40/30/30.
    corpus = generar({"alto": 137, "medio": 101, "bajo": 92})
    with open("corpus-sintetico.jsonl", "w", encoding="utf-8") as f:
        for ej in corpus:
            f.write(json.dumps(ej, ensure_ascii=False) + "\n")
    conteo = {}
    for ej in corpus:
        r = ej["messages"][1]["content"].split("\n")[0].replace("RIESGO: ", "")
        conteo[r] = conteo.get(r, 0) + 1
    print("corpus-sintetico.jsonl: %d ejemplos" % len(corpus))
    for k in ("alto", "medio", "bajo"):
        print("  %-6s %3d  (%.0f%%)" % (k, conteo.get(k, 0), 100.0 * conteo.get(k, 0) / len(corpus)))
    print("\nSiguiente: python mezclar_corpus.py")
