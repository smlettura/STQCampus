"""Módulo de IA — espacio reservado. Gemma 2 9B se usa sin reentrenamiento, configurado con un Modelfile; la inferencia
aún no está conectada a la plataforma y no se genera contenido.

La pantalla «Generar informe (IA)» del prototipo v1 ya existe (ver `views.generar_informe`) y muestra los datos reales que
usaría el módulo, pero el botón «Generar informe» queda deshabilitado mientras `DISPONIBLE` sea False.

Contrato que debe cumplir la implementación que reemplace a `generar_borrador` (requisitos RF-16 a RF-19 y RNF-11):

1. Permisos (RF-16): solo quien tiene el permiso «ia.usar» y puede ver las notas del caso (`apps.casos.acceso`). Debe
   existir un consentimiento vigente del apoderado con alcance «uso_ia» (`Consentimiento.vigente_para`).
2. Minimización (RNF-11): se envían solo las atenciones que la profesional marcó, reemplazando nombres, RUT, curso,
   apoderados y profesionales por seudónimos ([ESTUDIANTE], [APODERADO_1], ...). Si tras seudonimizar queda un dato
   identificable, la solicitud se bloquea y no sale nada del colegio.
3. Etiquetado (RF-18): el resultado se guarda en `ContenidoIA` con `etiqueta_ia=True` y estado «generado». El texto
   queda cifrado (AES-256-GCM) como el resto de la información sensible.
4. Validación humana (RF-18): ningún borrador pasa a un `Informe` sin que una profesional lo valide (estado «validado»,
   validador y fecha). La IA no emite diagnósticos ni decide ingresos o egresos del PIE.
5. Trazabilidad (RF-19): cada llamada al modelo se registra en `LlamadaModelo` con el hash SHA-256 de lo enviado (nunca
   el texto) y un evento en la bitácora de auditoría. Las fuentes normativas usadas quedan en `ContenidoIAFuente`.
6. Retroalimentación (RF-19): las profesionales pueden marcar una salida como incorrecta o problemática
   (`RetroalimentacionIA`), insumo para ajustar el Modelfile y los ejemplos anonimizados (sin reentrenar).
"""

DISPONIBLE = False

TIPOS_INFORME = [("atencion", "Informe de atención"), ("derivacion_externa", "Derivación externa"),
                 ("apoderado", "Informe para apoderado"), ("direccion", "Informe para dirección")]
SECCIONES = [("antecedentes", "Antecedentes"), ("desarrollo", "Desarrollo de las sesiones"),
             ("acuerdos", "Acuerdos y compromisos"), ("sugerencias", "Sugerencias de seguimiento")]
SECCIONES_POR_DEFECTO = ("antecedentes", "desarrollo", "acuerdos")
PERIODOS = [(1, "Último mes"), (3, "Últimos 3 meses"), (6, "Últimos 6 meses"), (12, "Último año")]


class ModuloIANoDisponible(Exception):
    """La inferencia del módulo de IA todavía no está disponible."""


def generar_borrador(*, estudiante, sesiones, tipo, secciones, usuario):
    """Punto de integración del módulo de IA. Hoy no genera nada: ver el contrato en la documentación del módulo."""
    raise ModuloIANoDisponible("El módulo de IA está en configuración: todavía no genera borradores. Redacte el informe "
                               "de forma manual desde la ficha del estudiante.")
