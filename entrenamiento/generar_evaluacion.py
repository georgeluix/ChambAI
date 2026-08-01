# -*- coding: utf-8 -*-
"""Genera evaluacion.jsonl: 20 casos escritos a mano, INTOCABLES.

A diferencia del corpus, estos avisos no salen de plantillas: imitan la
redaccion real de Facebook/WhatsApp (emojis, mayusculas, faltas de ortografia).
Si el modelo acierta aqui es porque generalizo, no porque memorizo el molde.

Uso: python generar_evaluacion.py
"""
import json
import re
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
from extractor import canonizar_bandera  # noqa: E402

PREFIJO = "Analiza este aviso de empleo:\n\n"

CASOS = [
    # ---------------------------- RIESGO ALTO ----------------------------
    ("""URGENTE!!! 🔥🔥 SE NECESITAN SEÑORITAS PARA NIGHT CLUB EN CUSCO 🔥🔥
De 18 a 25 añitos, buena presencia. GANAS 400 SOLES DIARIOS + propinas 💰
Nosotros te pagamos el pasaje y tienes donde quedarte en el mismo local.
No necesitas experiencia, aca te enseñamos todo. Solo WSP 987 654 321 📲""",
     "alto",
     ["Filtro por sexo, edad y apariencia fisica sin relacion con la funcion",
      "Remuneracion desproporcionada para el puesto y sin sustento",
      "Traslado a otra ciudad con pasaje cubierto por el empleador",
      "Alojamiento dentro del centro de trabajo",
      "Empleador no identificado: sin razon social ni RUC",
      "Contacto unicamente por mensajeria con un numero personal"],
     "El aviso reune seis señales de captacion, encabezadas por el filtro por edad y apariencia y el traslado con alojamiento en el propio local, que es el mecanismo clasico para aislar a la victima. No respondas ni envies datos; reporta a la Linea 1818."),

    ("""Se busca cocinera para campamento minero en Puerto Maldonado.
Sueldo 3500 soles mensuales, todo pagado. Viaje el domingo, la empresa cubre el pasaje.
Son 45 dias adentro sin salir. Traer DNI, se queda en oficina por seguridad.
Interesadas escribir a Karla 912 445 778""",
     "alto",
     ["Traslado inmediato a zona de alto riesgo con pasaje cubierto por el empleador",
      "Permanencia prolongada en el centro de trabajo sin posibilidad de salida",
      "Retencion del documento de identidad",
      "Empleador no identificado: sin razon social ni RUC",
      "Contacto unicamente por mensajeria con un numero personal"],
     "La combinacion de traslado pagado a una zona de mineria informal, encierro de 45 dias y entrega del DNI describe condiciones de explotacion laboral, no un empleo formal. La retencion de documentos es delito. No viajes y denuncia al 1818."),

    ("""Chicas para trabajar en IQUITOS 🌴 atencion a clientes en reservados
Turno de 9pm a 4am. Pago diario en efectivo, ganas bien.
Alojamiento incluido arriba del local. Discrecion total, no es necesario que tu familia sepa.
Escribeme al privado""",
     "alto",
     ["Servicios de acompañamiento en local privado y horario nocturno",
      "Alojamiento dentro del centro de trabajo",
      "Exigencia de confidencialidad frente al entorno familiar",
      "Empleador no identificado: sin razon social ni RUC"],
     "Pedir que la familia no se entere, sumado al alojamiento en el mismo local nocturno, es un patron de aislamiento propio de la trata con fines de explotacion sexual. Ningun empleo legitimo exige ocultarse del entorno. Denuncia a la Linea 1818."),

    ("""OPORTUNIDAD UNICA - ULTIMAS 3 VACANTES - EMPIEZAS HOY
Trabajo facil, no pedimos CV ni experiencia. 2500 soles a la semana.
Solo necesitas depositar 200 soles para tu examen medico y uniforme (se te devuelve).
Yapea al 956 332 118 y separas tu cupo AHORA""",
     "alto",
     ["Cobro adelantado al postulante",
      "Remuneracion desproporcionada para el puesto y sin sustento",
      "Presion de urgencia para impedir verificacion",
      "Ausencia total de requisitos",
      "Empleador no identificado: sin razon social ni RUC"],
     "Ningun empleador formal cobra al postulante: ese solo hecho descarta la oferta. Sumado a la urgencia artificial y al sueldo irreal, es una estafa o un enganche de captacion. No deposites nada y reporta el numero."),

    ("""Casting para modelos de catalogo, no se necesita experiencia.
Enviar 4 fotos de cuerpo entero (una en ropa de baño) + medidas al wsp.
La entrevista es en el Hotel Continental, te paso el numero de habitacion por interno.
Pago 800 soles por sesion. Solo mayores de 18 con MUY buena presencia.""",
     "alto",
     ["Solicitud de fotografias de cuerpo entero en ropa de baño",
      "Entrevista en habitacion de hotel en lugar de sede de la empresa",
      "Filtro por apariencia fisica sin relacion con la funcion",
      "Empleador no identificado: sin razon social ni RUC"],
     "Pedir fotos en ropa de baño por WhatsApp y citar en una habitacion de hotel no corresponde a ningun casting profesional; son señales de captacion con fines de explotacion sexual. No envies imagenes ni acudas a la cita y reporta a la Linea 1818."),

    ("""Familia en Arica (Chile) busca empleada del hogar cama adentro.
Sueldo 900 dolares, comida y cuarto incluidos. Nosotros tramitamos tu viaje y te damos el pasaje.
Necesitamos tu DNI y partida de nacimiento por adelantado para el tramite.
Salida la proxima semana. Contactar por WhatsApp unicamente.""",
     "alto",
     ["Traslado internacional con pasaje y tramites cubiertos por el empleador",
      "Solicitud de documentos personales antes de cualquier contrato",
      "Alojamiento en el domicilio del empleador bajo modalidad cama adentro",
      "Contacto unicamente por mensajeria con un numero personal"],
     "El traslado internacional pagado por un tercero que ademas retiene tus documentos es el esquema mas frecuente de trata transfronteriza; una vez fuera del pais quedas sin red de apoyo. No entregues documentos originales y consulta antes a la Linea 1818."),

    ("""se necesitan damas de compañia para restobar en la av. angamos
buen ambiente, ganas desde 300 diarios mas comisiones
no importa si no tienes experiencia, solo actitud
trabajo discreto, aqui nadie pregunta nada
escribir al 973 118 402, preguntar por el señor Vega""",
     "alto",
     ["Servicios de acompañamiento en local nocturno",
      "Remuneracion desproporcionada para el puesto y sin sustento",
      "Exigencia de discrecion sobre la naturaleza del trabajo",
      "Empleador no identificado: sin razon social ni RUC",
      "Contacto unicamente por mensajeria con un numero personal"],
     "La categoria dama de compañia junto con la promesa de discrecion y un pago diario desproporcionado configura una oferta de explotacion encubierta. El anonimato del empleador impide cualquier reclamo posterior. Reporta el aviso a la Linea 1818."),

    ("""Buscamos chicas desde 16 años para atencion en bar karaoke 🎤
No importa que estes estudiando, el horario es de noche nomas.
Te damos adelanto el primer dia. Movilidad de regreso incluida.
Interesadas mandar foto y edad al wsp 981 220 397""",
     "alto",
     ["Convocatoria dirigida a menores de edad",
      "Trabajo nocturno en local de expendio de alcohol para menores",
      "Solicitud de fotografia personal como filtro",
      "Adelanto de dinero como mecanismo de enganche",
      "Contacto unicamente por mensajeria con un numero personal"],
     "Convocar a menores de edad para trabajo nocturno en un local de alcohol es delito en si mismo, y el adelanto de dinero es el inicio tipico de una deuda que ata a la victima. Denuncia de inmediato a la Linea 1818 y a la Policia."),

    # ---------------------------- RIESGO MEDIO ---------------------------
    ("""Contact Center Lima Norte necesita teleoperadores para turno noche (10pm a 6am).
Se paga bono nocturno de ley y hay movilidad de retorno.
El sueldo lo conversamos en la entrevista, depende de tu perfil.
Coordinar por WhatsApp 991 447 203 con el area de reclutamiento.""",
     "medio",
     ["Remuneracion no especificada en el aviso",
      "Trabajo en horario nocturno",
      "Postulacion unicamente por mensajeria"],
     "La empresa esta identificada y menciona bono nocturno y movilidad, lo que apunta a formalidad, pero omitir el sueldo y postular solo por WhatsApp impide verificar la oferta. Confirma el RUC en SUNAT y pide que la entrevista sea en la sede antes de asistir."),

    ("""Distribuidora Sol Naciente busca asesores comerciales.
Ingresos ILIMITADOS, todo depende de cuanto vendas. Nuestros mejores asesores ganan 6000 al mes.
No pedimos experiencia, nosotros te capacitamos. Sin sueldo base los primeros 2 meses.
Escribir al 954 887 100.""",
     "medio",
     ["Remuneracion variable sin sueldo base durante dos meses",
      "Promesa de ingresos elevados sin sustento",
      "Ausencia de requisitos de experiencia",
      "Postulacion unicamente por mensajeria"],
     "No hay señales de trata, pero un esquema sin sueldo base durante dos meses traslada todo el riesgo al trabajador y vulnera el derecho a la remuneracion minima. Exige contrato por escrito con las condiciones de comision antes de aceptar."),

    ("""Agroindustrial Chavimochic requiere operarios de campo para la planta de Viru.
Se cubre alojamiento en campamento, regimen 14x7. Contrato en planilla agraria.
Sueldo segun tarifario del sector. Salida desde Trujillo cada quincena.
Postular en la oficina de RRHH de la planta o al correo seleccion@chavimochic.com.pe""",
     "medio",
     ["Trabajo fuera de la ciudad de residencia con alojamiento provisto",
      "Remuneracion referida a un tarifario no detallado en el aviso"],
     "La convocatoria identifica a la empresa, ofrece contrato en planilla y un canal institucional, lo que la aleja del perfil de captacion. El alojamiento en campamento es normal en el sector agroindustrial; aun asi, confirma las condiciones por escrito antes de trasladarte."),

    ("""Restaurante en Miraflores necesita ayudante de cocina.
Pago 60 soles el dia, en efectivo cada semana. Por ahora sin contrato, mas adelante vemos planilla.
Horario de 11am a 9pm, un dia libre. Preguntar por doña Rosa en el local, jiron Berlin 340.""",
     "medio",
     ["Sin contrato ni ingreso a planilla",
      "Pago en efectivo sin boleta"],
     "La informalidad laboral es real y te deja sin EsSalud ni beneficios, pero el aviso da direccion fisica verificable, horario concreto y un pago acorde al mercado, sin ninguna señal de captacion. Exige contrato desde el primer dia antes de empezar."),

    ("""Emprendimiento de reposteria busca asistente de produccion.
Somos un negocio familiar que recien esta creciendo, todavia estamos formalizando.
Sueldo 1200 mensuales, horario de lunes a sabado de 7am a 3pm en nuestro taller de San Martin de Porres.
Enviar CV a pasteleriadulcemaria@gmail.com""",
     "medio",
     ["Empresa en proceso de formalizacion, sin RUC en el aviso",
      "Correo de contacto no corporativo"],
     "El aviso es coherente: funciones claras, horario definido, sueldo acorde y direccion del taller. La falta de RUC refleja informalidad de un negocio pequeño, no un intento de ocultamiento. Verifica la existencia del taller y solicita contrato antes de iniciar."),

    ("""Seguridad Integral Andes S.A.C. contrata agentes de seguridad para turno noche.
Requisitos: licencia SUCAMEC vigente, secundaria completa, certificado de antecedentes.
Sueldo 1450 en planilla con todos los beneficios.
Interesados escribir al WhatsApp 998 771 034, no llamar.""",
     "medio",
     ["Postulacion unicamente por mensajeria personal",
      "Trabajo en horario nocturno"],
     "La oferta es solida: razon social, licencia SUCAMEC como requisito, sueldo explicito y planilla. El unico punto debil es el canal de contacto, que no permite verificar quien esta del otro lado. Pide ser derivada a la oficina de RRHH de la empresa."),

    # ---------------------------- RIESGO BAJO ----------------------------
    ("""Supermercados Mi Barrio S.A.C. (RUC 20512447890) convoca a cajeros para su tienda de Los Olivos.
Requisitos: secundaria completa, experiencia minima de 6 meses en manejo de efectivo, disponibilidad para turnos rotativos diurnos.
Ofrecemos: S/ 1350 mensuales en planilla, EsSalud, gratificaciones, CTS y descuento de personal.
Postular en nuestra bolsa de trabajo: empleos.mibarrio.com.pe""",
     "bajo", None,
     "El aviso identifica a la empresa con RUC, detalla requisitos proporcionales al puesto, indica una remuneracion acorde al mercado y ofrece los beneficios de ley con un canal de postulacion institucional. No se observan señales de captacion."),

    ("""Municipalidad Distrital de Santiago de Surco - Convocatoria CAS N° 018-2026
Puesto: asistente administrativo para la Gerencia de Desarrollo Social (1 vacante).
Requisitos: bachiller en administracion o afines, 2 años de experiencia en el sector publico.
Remuneracion: S/ 3000 mensuales. Bases y cronograma publicados en el portal institucional de la municipalidad.""",
     "bajo", None,
     "Se trata de una convocatoria publica con numero de proceso, bases publicadas y perfil detallado, sujeta al regimen CAS. La trazabilidad del proceso descarta cualquier riesgo de captacion."),

    ("""Clinica San Marcos requiere licenciada en enfermeria para el area de hospitalizacion.
Requisitos indispensables: titulo universitario, colegiatura y habilitacion vigente en el Colegio de Enfermeros del Peru, 2 años de experiencia hospitalaria.
Turnos rotativos segun rol, contrato a plazo indeterminado, S/ 2800 mas guardias.
Enviar CV documentado a seleccion@clinicasanmarcos.com.pe""",
     "bajo", None,
     "Exigir titulo, colegiatura y habilitacion vigente es propio de un empleador formal en el sector salud, y las condiciones contractuales estan explicitas. El correo corporativo permite verificar al remitente. No hay indicadores de riesgo."),

    ("""Quimtec Labs busca desarrollador backend Python (modalidad remota desde Peru).
Requisitos: 3 años con FastAPI o Django, experiencia con PostgreSQL y Docker, ingles tecnico.
Ofrecemos: banda salarial de S/ 6500 a S/ 9000 segun evaluacion tecnica, contrato en planilla, EPS y 15 dias de vacaciones adicionales.
Proceso: prueba tecnica, entrevista con el equipo y oferta. Postula en nuestro LinkedIn.""",
     "bajo", None,
     "El sueldo es alto pero corresponde al mercado real de desarrolladores con ese stack y esta justificado por requisitos tecnicos verificables y un proceso de seleccion por etapas. Empleador y canal son identificables. Riesgo bajo."),

    ("""Transportes Huascaran E.I.R.L. (RUC 20447119023) necesita chofer de reparto para Lima Metropolitana.
Requisitos: licencia A-IIB vigente, certificado de antecedentes penales y policiales, experiencia minima de 1 año en reparto urbano.
S/ 1800 en planilla mas asignacion familiar y movilidad. Horario de lunes a sabado de 7:00 a 16:00.
Presentar CV en nuestro local de Av. Argentina 2145, Cercado de Lima, de lunes a viernes.""",
     "bajo", None,
     "La empresa figura con RUC y direccion fisica donde se recibe la documentacion, los requisitos son verificables y las condiciones se ajustan a la normativa laboral. Nada en el aviso sugiere riesgo."),

    ("""ONG Manos Unidas convoca a asistente de proyectos sociales (Cusco).
Perfil: licenciado en trabajo social, sociologia o afines; 2 años de experiencia en proyectos con poblacion vulnerable; disponibilidad para viajes a provincias del departamento con viaticos cubiertos y programados.
Contrato por 12 meses renovable, S/ 3200 mensuales en planilla.
Enviar CV y carta de motivacion a convocatorias@manosunidas.org.pe hasta el 15 de agosto.""",
     "bajo", None,
     "Aunque el puesto incluye viajes, estos estan programados, con viaticos y dentro de un contrato formal de 12 meses, que es lo contrario al traslado inmediato e improvisado de las ofertas de captacion. Organizacion, plazo y canal son verificables."),
]


def formatear(nivel, banderas, explicacion):
    canonicas = []
    for bandera in banderas or []:
        for canonica in canonizar_bandera(bandera):
            if canonica not in canonicas:
                canonicas.append(canonica)
    lineas = ["- " + b for b in canonicas] if canonicas else ["- Ninguna señal de alerta detectada"]
    return "RIESGO: %s\nBANDERAS:\n%s\nEXPLICACION: %s" % (nivel, "\n".join(lineas), explicacion)


def anonimizar(texto):
    """Impide que los datos ficticios coincidan con una persona o empresa real."""
    texto = re.sub(r"\b9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b", "9XX XXX XXX", texto)
    texto = re.sub(r"\b20\d{9}\b", "20XXXXXXXXX", texto)
    texto = re.sub(
        r"\b([\w.+-]+)@[\w.-]+\.[a-z]{2,}\b",
        lambda m: m.group(1) + "@empresa-ejemplo.invalid",
        texto,
        flags=re.I,
    )
    return texto


if __name__ == "__main__":
    with open("evaluacion.jsonl", "w", encoding="utf-8") as f:
        for aviso, nivel, banderas, expl in CASOS:
            aviso = anonimizar(" ".join(l.strip() for l in aviso.strip().splitlines()))
            f.write(json.dumps({
                "origen": "evaluacion-manual",
                "tipo": "sintetico",
                "fuente": "Casos de evaluacion redactados manualmente por el equipo",
                "messages": [
                {"role": "user", "content": PREFIJO + aviso},
                {"role": "assistant", "content": formatear(nivel, banderas, expl)},
            ]}, ensure_ascii=False) + "\n")
    conteo = {}
    for _, nivel, _, _ in CASOS:
        conteo[nivel] = conteo.get(nivel, 0) + 1
    print("evaluacion.jsonl: %d ejemplos" % len(CASOS))
    for k in ("alto", "medio", "bajo"):
        print("  %-6s %2d" % (k, conteo.get(k, 0)))
