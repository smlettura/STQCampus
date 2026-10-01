"""Exportación del expediente (acceso y portabilidad, RNF-13) y política de retención de 15 años (RNF-10, BPMN B5)."""
import json

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.auditoria.servicios import registrar
from apps.casos import almacenamiento
from apps.casos.models import Caso
from apps.core.validadores import sumar_anios
from apps.estudiantes.models import Apoderado, Estudiante

from .models import RetencionEliminacion


def _f(valor):
    return valor.isoformat() if valor else None


def exportar_expediente(estudiante, usuario, incluir_clinico):
    """Expediente completo en JSON (formato estructurado y reutilizable). El contenido clínico solo se incluye si
    quien exporta pertenece al equipo psicosocial."""
    datos = {
        "generado": timezone.now().isoformat(), "plataforma": settings.NOMBRE_PLATAFORMA,
        "estudiante": {"rut": estudiante.rut, "primer_nombre": estudiante.primer_nombre,
                       "segundo_nombre": estudiante.segundo_nombre, "apellido_paterno": estudiante.apellido_paterno,
                       "apellido_materno": estudiante.apellido_materno, "nombre_social": estudiante.nombre_social,
                       "fecha_ingreso": _f(estudiante.fecha_ingreso), "prioritario": estudiante.prioritario,
                       "tipo_salida": estudiante.get_tipo_salida_display(),
                       "fecha_nacimiento": _f(estudiante.fecha_nacimiento), "curso": str(estudiante.curso),
                       "necesidad_educativa": estudiante.get_necesidad_educativa_display(), "en_pie": estudiante.en_pie,
                       "matricula_condicional": estudiante.matricula_condicional, "fecha_egreso": _f(estudiante.fecha_egreso)},
        "anotaciones": [{"fecha": _f(a.fecha), "tipo": a.get_tipo_display(), "descripcion": a.descripcion}
                        for a in estudiante.anotaciones.all()],
        "situacion_conductual": [{"fecha": _f(r.fecha), "categoria": r.get_categoria_display(), "descripcion": r.descripcion,
                                  "porcentaje_asistencia": float(r.porcentaje_asistencia)
                                  if r.porcentaje_asistencia is not None else None}
                                 for r in estudiante.registros_conductuales.all()],
        "apoderados": [{"rut": v.apoderado.rut, "nombre": v.apoderado.nombre_completo, "parentesco": v.get_parentesco_display(),
                        "titular": v.es_titular, "telefono": v.apoderado.telefono, "correo": v.apoderado.correo}
                       for v in estudiante.vinculos_apoderado.select_related("apoderado")],
        "consentimientos": [{"alcance": c.get_alcance_display(), "otorgado": _f(c.fecha_otorgamiento),
                             "revocado": _f(c.fecha_revocacion)} for c in estudiante.consentimientos.all()],
        "planes_de_apoyo": [{"tipo": p.get_tipo_display(), "inicio": _f(p.fecha_inicio), "termino": _f(p.fecha_termino),
                             "adecuaciones": p.adecuaciones, **({"detalle": p.detalle} if incluir_clinico else {})}
                            for p in estudiante.planes.all()],
        "casos": [],
    }
    for caso in estudiante.casos.all():
        c = {"tipo_proceso": caso.get_tipo_proceso_display(), "estado": caso.get_estado_display(),
             "apertura": _f(caso.fecha_apertura), "cierre": _f(caso.fecha_cierre),
             "hitos": [{"fecha": _f(h.fecha), "tipo": h.get_tipo_display(), "descripcion": h.descripcion}
                       for h in caso.hitos.all()],
             "documentos": [{"nombre": d.nombre_archivo, "tipo": d.get_tipo_display(), "sha256": d.hash_sha256}
                            for d in caso.documentos.all()],
             "informes_entregados": [{"tipo": i.get_tipo_display(), "entrega": _f(i.fecha_entrega)}
                                     for i in caso.informes.filter(estado="entregado")]}
        if incluir_clinico:
            c["atenciones"] = [{"fecha_hora": _f(s.fecha_hora), "duracion_minutos": s.duracion_minutos,
                                "tipo": s.get_tipo_atencion_display(), "motivo": s.get_motivo_display(),
                                "descripcion": s.nota, "acuerdos": s.acuerdos}
                               for s in caso.sesiones.filter(nivel_acceso="equipo", estado="registrada")]
            c["evaluaciones"] = [{"fecha": _f(e.fecha_evaluacion), "tipo_nee": e.tipo_nee, "diagnostico": e.diagnostico}
                                 for e in caso.evaluaciones.all()]
        datos["casos"].append(c)
    if not incluir_clinico:
        datos["nota"] = "El contenido clínico (notas y diagnósticos) lo entrega el equipo psicosocial."
    registrar(usuario, "exportacion", "estudiante", estudiante.pk, detalle="expediente %s" % ("completo" if incluir_clinico else "administrativo"))
    return json.dumps(datos, ensure_ascii=False, indent=2)


def fecha_vencimiento(estudiante):
    """15 años desde el egreso del estudiante o desde el cierre de su último caso, lo que ocurra después.
    Si tiene casos abiertos, o aún no egresa, no hay vencimiento."""
    if estudiante.casos.exclude(estado="cerrado").exists():
        return None
    ultimo_cierre = estudiante.casos.aggregate(m=Max("fecha_cierre"))["m"]
    base = max([f for f in (estudiante.fecha_egreso, ultimo_cierre) if f], default=None)
    if not estudiante.fecha_egreso or base is None:
        return None
    return sumar_anios(base, settings.RETENCION_ANIOS)


@transaction.atomic
def proponer_retenciones(hoy=None):
    """Tarea mensual: propone a la Directora los expedientes cuyo plazo venció. No elimina nada."""
    hoy = hoy or timezone.localdate()
    candidatos = Estudiante.objects.filter(fecha_egreso__isnull=False, fecha_egreso__lte=hoy)
    candidatos = candidatos.exclude(retenciones__estado__in=["propuesta", "autorizada", "postergada", "ejecutada"])
    creadas = 0
    for e in candidatos:
        vence = fecha_vencimiento(e)
        if vence and vence <= hoy:
            r = RetencionEliminacion.objects.create(estudiante=e, fecha_vencimiento=vence)
            registrar(None, "creacion", "retencion_eliminacion", r.pk)
            creadas += 1
    return creadas


@transaction.atomic
def autorizar(retencion, directora, accion, autoriza=True):
    retencion.accion = accion
    if autoriza:
        retencion.estado, retencion.autorizada_por, retencion.fecha_autorizacion = "autorizada", directora, timezone.now()
    else:
        retencion.estado = "postergada"
    retencion.full_clean()
    retencion.save()
    registrar(directora, "modificacion", "retencion_eliminacion", retencion.pk, detalle=retencion.estado)
    return retencion


@transaction.atomic
def ejecutar(retencion):
    """Ejecuta una eliminación o anonimización ya autorizada por la Directora."""
    if retencion.estado != "autorizada" or not retencion.autorizada_por_id:
        raise PermissionError("La eliminación no está autorizada.")
    e = retencion.estudiante
    if e is None:
        raise ValueError("El expediente ya no existe.")
    id_estudiante = e.pk
    ids_apoderados = list(e.vinculos_apoderado.values_list("apoderado_id", flat=True))
    if retencion.accion == "eliminar":
        for caso in e.casos.all():
            for doc in caso.documentos.all():
                almacenamiento.eliminar_archivo(doc)
        e.delete()
    else:
        _anonimizar(e)
    # Apoderados que ya no se vinculan con ningún estudiante tampoco se conservan.
    Apoderado.objects.filter(pk__in=ids_apoderados, vinculos_estudiante__isnull=True, consentimientos__isnull=True,
                             solicitudes_arco__isnull=True).delete()
    retencion.refresh_from_db()
    retencion.estado, retencion.fecha_ejecucion = "ejecutada", timezone.now()
    retencion.save(update_fields=["estado", "fecha_ejecucion"])
    registrar(None, "eliminacion", "estudiante", id_estudiante, detalle="retención: %s" % retencion.accion)
    return retencion


def _anonimizar(e):
    """Anonimización irreversible: se eliminan identificadores y contenido clínico; quedan datos agregables."""
    for caso in Caso.objects.filter(estudiante=e):
        for doc in caso.documentos.all():
            almacenamiento.eliminar_archivo(doc)
        caso.documentos.all().delete()
        caso.sesiones.all().delete()
        caso.hitos.all().delete()
        caso.derivaciones.all().delete()
        caso.contenidos_ia.all().delete()           # tabla reservada del módulo de IA
        caso.informes.all().delete()
        for ev in caso.evaluaciones.all():
            ev.participaciones.all().delete()
            ev.diagnostico = ""
            ev.save(update_fields=["diagnostico"])
        caso.tipo_atencion = ""
        caso.save(update_fields=["tipo_atencion"])
    e.alertas.all().delete()
    e.consentimientos.all().delete()
    e.solicitudes_arco.all().delete()
    e.planes.all().delete()
    e.vinculos_apoderado.all().delete()
    # Anotaciones y situación conductual: se conserva el tipo y la fecha (agregables), no el relato.
    e.anotaciones.update(descripcion="Registro anonimizado.")
    e.registros_conductuales.update(descripcion="Registro anonimizado.")
    e.protocolos.update(estudiante=None)
    for conflicto in e.conflictos.all():
        conflicto.participantes.remove(e)
    e.rut = "ANON-%d" % e.pk
    e.primer_nombre, e.segundo_nombre, e.nombre_social = "Registro", "", ""
    e.apellido_paterno, e.apellido_materno = "anonimizado", "anonimizado"
    e.fecha_nacimiento = e.fecha_nacimiento.replace(month=1, day=1)
    e.fecha_ingreso = None
    e.save()

