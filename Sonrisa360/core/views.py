"""Vistas de Sonrisa360: permisos por rol y validación en servidor.

Conserva la tabla core_usuario existente para actualizar sin perder registros.
"""
from datetime import time
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.http import require_POST
from .models import Usuario, Paciente, Medico, Consultorio, Cita, EspecialidadMedico, HorarioMedico, Cotizacion, ItemCotizacion
from .forms import CuentaForm, PacienteForm, MedicoForm, ConsultorioForm, CitaForm, CotizacionForm, ItemCotizacionForm, HorarioForm
from .auth import ADMIN, MEDADMIN, MEDICO, PACIENTE, GESTORES, clinic_login_required, usuario_actual, sello_sesion


class TokenRecuperacion(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.contrasenia}{user.activo}{timestamp}{user.correo_electronico}"


tokens = TokenRecuperacion()


def login_view(request):
    if usuario_actual(request):
        return redirect("dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        # Límite de intentos por IP y usuario (en memoria; Redis para producción).
        clave = "intentos_login:" + str(request.META.get("REMOTE_ADDR", "")) + ":" + username.lower()
        if cache.get(clave, 0) >= 8:
            messages.error(request, "Demasiados intentos. Intenta nuevamente más adelante.")
        else:
            usuario = Usuario.objects.filter(usuario__iexact=username, activo=True).first()
            if usuario and usuario.check_password(password):
                request.session.flush()
                request.session["usuario_id"] = usuario.pk
                request.session["clinic_sello"] = sello_sesion(usuario)
                request.session.set_expiry(8 * 3600)
                cache.delete(clave)
                messages.success(request, f"Bienvenido a Sonrisa360, {usuario.usuario}.")
                return redirect("dashboard")
            cache.set(clave, cache.get(clave, 0) + 1, 15 * 60)
            messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, "core/login.html")


@clinic_login_required()
@require_POST
def logout_view(request):
    request.session.flush()
    messages.info(request, "Sesión cerrada.")
    return redirect("login")


@clinic_login_required()
def dashboard_view(request):
    usuario = usuario_actual(request)
    contexto = {"perfil": usuario.rol}
    hoy = timezone.localdate()
    if usuario.rol in GESTORES:
        contexto.update(total_pacientes=Paciente.objects.filter(activo=True).count(),
                        total_medicos=Medico.objects.filter(activo=True).count(),
                        total_consultorios=Consultorio.objects.filter(activo=True).count())
        qs = Cita.objects.filter(fecha__gte=hoy).exclude(estado="cancelada")
    elif usuario.rol == MEDICO:
        medico = get_object_or_404(Medico, usuario=usuario, activo=True)
        contexto["medico_actual"] = medico
        contexto["total_citas"] = Cita.objects.filter(medico=medico).count()
        qs = Cita.objects.filter(medico=medico, fecha__gte=hoy).exclude(estado="cancelada")
    else:
        paciente = get_object_or_404(Paciente, usuario=usuario, activo=True)
        contexto["paciente_actual"] = paciente
        contexto["total_citas"] = Cita.objects.filter(paciente=paciente).count()
        contexto["total_cotizaciones"] = Cotizacion.objects.filter(cita__paciente=paciente).exclude(estado="borrador").count()
        qs = Cita.objects.filter(paciente=paciente, fecha__gte=hoy).exclude(estado="cancelada")
    contexto["proximas_citas"] = qs.select_related("paciente", "medico").order_by("fecha", "hora")[:6]
    if usuario.rol == ADMIN:
        plantilla = "core/dashboard.html"
    elif usuario.rol == MEDADMIN:
        plantilla = "core/dashboard_medadmin.html"
    else:
        plantilla = "core/dashboard_perfil.html"
    return render(request, plantilla, contexto)


def _render_errors(request, *forms):
    for form in forms:
        for campo, errores in form.errors.items():
            for error in errores:
                messages.error(request, f"{campo}: {error}")


def _guardar_cuenta(request, perfil_form, cuenta_form, *, rol, cuenta=None):
    if not (perfil_form.is_valid() and cuenta_form.is_valid()):
        _render_errors(request, perfil_form, cuenta_form)
        return None
    try:
        with transaction.atomic():
            if cuenta is None:
                cuenta = Usuario(rol=rol)
            cuenta.rol = rol
            cuenta.usuario = cuenta_form.cleaned_data["usuario"]
            cuenta.correo_electronico = cuenta_form.cleaned_data["correo_electronico_usuario"]
            if cuenta_form.cleaned_data["contrasenia"]:
                cuenta.set_password(cuenta_form.cleaned_data["contrasenia"])
            cuenta.save()
            perfil = perfil_form.save(commit=False)
            perfil.usuario = cuenta
            perfil.save()
            return perfil
    except (IntegrityError, ValidationError):
        messages.error(request, "No se pudo guardar. Comprueba que el usuario y el documento sean únicos.")
        return None


@clinic_login_required(ADMIN, MEDADMIN)
def pacientes_list(request):
    return render(request, "core/pacientes/list.html", {
        "pacientes": Paciente.objects.filter(activo=True).order_by("nombre_paciente")})


@clinic_login_required(ADMIN, MEDADMIN, MEDICO)
def paciente_detail(request, pk):
    usuario = usuario_actual(request)
    qs = Paciente.objects.filter(activo=True)
    if usuario.rol == MEDICO:
        qs = qs.filter(cita__medico__usuario=usuario).distinct()
    return render(request, "core/pacientes/detail.html", {"paciente": get_object_or_404(qs, pk=pk)})


@clinic_login_required(ADMIN)
def paciente_create(request):
    if request.method == "POST":
        perfil_form = PacienteForm(request.POST)
        cuenta_form = CuentaForm(request.POST, nueva=True)
        if _guardar_cuenta(request, perfil_form, cuenta_form, rol=PACIENTE):
            messages.success(request, "Paciente registrado correctamente.")
            return redirect("pacientes_list")
    return render(request, "core/pacientes/form.html")


@clinic_login_required(ADMIN)
def paciente_edit(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        perfil_form = PacienteForm(request.POST, instance=paciente)
        cuenta_form = CuentaForm(request.POST, cuenta=paciente.usuario)
        if _guardar_cuenta(request, perfil_form, cuenta_form, rol=PACIENTE, cuenta=paciente.usuario):
            messages.success(request, "Paciente actualizado.")
            return redirect("pacientes_list")
    return render(request, "core/pacientes/form.html", {"paciente": paciente})


@clinic_login_required(ADMIN)
def paciente_delete(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        if Cita.objects.filter(paciente=paciente, fecha__gte=timezone.localdate(), estado__in=["programada", "reprogramada"]).exists():
            messages.error(request, "Primero cancela o reasigna las citas futuras del paciente.")
            return redirect("paciente_detail", pk=pk)
        paciente.activo = False
        paciente.save(update_fields=["activo"])
        paciente.usuario.activo = False
        paciente.usuario.save(update_fields=["activo"])
        messages.success(request, "Paciente desactivado; se conserva su historial.")
        return redirect("pacientes_list")
    return render(request, "core/pacientes/delete.html", {"paciente": paciente})


@clinic_login_required(ADMIN, MEDADMIN)
def medicos_list(request):
    return render(request, "core/medicos/list.html", {
        "medicos": Medico.objects.filter(activo=True).select_related("especialidad").order_by("nombre_medico")})


@clinic_login_required(ADMIN, MEDADMIN, MEDICO)
def medico_detail(request, pk):
    usuario = usuario_actual(request)
    qs = Medico.objects.filter(activo=True)
    if usuario.rol == MEDICO:
        qs = qs.filter(usuario=usuario)
    return render(request, "core/medicos/detail.html", {"medico": get_object_or_404(qs, pk=pk)})


@clinic_login_required(ADMIN)
def medico_create(request):
    if request.method == "POST":
        perfil_form = MedicoForm(request.POST)
        cuenta_form = CuentaForm(request.POST, nueva=True)
        medico = _guardar_cuenta(request, perfil_form, cuenta_form, rol=MEDADMIN if request.POST.get("rol") == MEDADMIN else MEDICO)
        if medico:
            # Horario inicial editable; no habilita atención los fines de semana automáticamente.
            for dia in range(5):
                HorarioMedico.objects.get_or_create(medico=medico, dia_semana=dia, hora_inicio=time(8), defaults={"hora_fin": time(18)})
            messages.success(request, "Médico registrado. Revisa su horario de atención.")
            return redirect("medicos_list")
    return render(request, "core/medicos/form.html", {"especialidades": EspecialidadMedico.objects.all(), "rol_actual": MEDICO})


@clinic_login_required(ADMIN)
def medico_edit(request, pk):
    medico = get_object_or_404(Medico, pk=pk)
    if request.method == "POST":
        perfil_form = MedicoForm(request.POST, instance=medico)
        cuenta_form = CuentaForm(request.POST, cuenta=medico.usuario)
        if _guardar_cuenta(request, perfil_form, cuenta_form, rol=MEDADMIN if request.POST.get("rol") == MEDADMIN else MEDICO, cuenta=medico.usuario):
            messages.success(request, "Médico actualizado.")
            return redirect("medicos_list")
    return render(request, "core/medicos/form.html", {"medico": medico, "especialidades": EspecialidadMedico.objects.all(), "rol_actual": medico.usuario.rol})


@clinic_login_required(ADMIN)
def medico_delete(request, pk):
    medico = get_object_or_404(Medico, pk=pk)
    if request.method == "POST":
        if Cita.objects.filter(medico=medico, fecha__gte=timezone.localdate(), estado__in=["programada", "reprogramada"]).exists():
            messages.error(request, "Primero reasigna o cancela las citas futuras del odontólogo.")
            return redirect("medico_detail", pk=pk)
        medico.activo = False
        medico.save(update_fields=["activo"])
        medico.usuario.activo = False
        medico.usuario.save(update_fields=["activo"])
        messages.success(request, "Médico desactivado; se conservaron sus citas.")
        return redirect("medicos_list")
    return render(request, "core/medicos/delete.html", {"medico": medico})


@clinic_login_required(ADMIN, MEDADMIN)
def consultorios_list(request):
    return render(request, "core/consultorios/list.html", {"consultorios": Consultorio.objects.filter(activo=True)})


@clinic_login_required(ADMIN, MEDADMIN)
def consultorio_detail(request, pk):
    return render(request, "core/consultorios/detail.html", {"consultorio": get_object_or_404(Consultorio, pk=pk, activo=True)})


@clinic_login_required(ADMIN)
def consultorio_create(request):
    if request.method == "POST":
        form = ConsultorioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Consultorio registrado.")
            return redirect("consultorios_list")
        _render_errors(request, form)
    return render(request, "core/consultorios/form.html")


@clinic_login_required(ADMIN)
def consultorio_edit(request, pk):
    consultorio = get_object_or_404(Consultorio, pk=pk, activo=True)
    if request.method == "POST":
        form = ConsultorioForm(request.POST, instance=consultorio)
        if form.is_valid():
            form.save()
            messages.success(request, "Consultorio actualizado.")
            return redirect("consultorios_list")
        _render_errors(request, form)
    return render(request, "core/consultorios/form.html", {"consultorio": consultorio})


@clinic_login_required(ADMIN)
def consultorio_delete(request, pk):
    consultorio = get_object_or_404(Consultorio, pk=pk, activo=True)
    if request.method == "POST":
        if Cita.objects.filter(consultorio=consultorio, fecha__gte=timezone.localdate(), estado__in=["programada", "reprogramada"]).exists():
            messages.error(request, "Primero reasigna o cancela las citas futuras del consultorio.")
            return redirect("consultorio_detail", pk=pk)
        consultorio.activo = False
        consultorio.save(update_fields=["activo"])
        messages.success(request, "Consultorio desactivado.")
        return redirect("consultorios_list")
    return render(request, "core/consultorios/delete.html", {"consultorio": consultorio})


def _citas_visibles(usuario):
    base = Cita.objects.select_related("paciente", "medico", "consultorio")
    if usuario.rol in GESTORES:
        return base
    if usuario.rol == MEDICO:
        return base.filter(medico__usuario=usuario)
    return base.filter(paciente__usuario=usuario)


@clinic_login_required()
def citas_list(request):
    citas = _citas_visibles(usuario_actual(request)).order_by("-fecha", "-hora")
    return render(request, "core/citas/list.html", {"citas": citas})


@clinic_login_required()
def cita_detail(request, pk):
    cita = get_object_or_404(_citas_visibles(usuario_actual(request)), pk=pk)
    return render(request, "core/citas/detail.html", {"cita": cita})


def _render_cita(request, cita=None):
    usuario = usuario_actual(request)
    paciente_propio = None
    if usuario.rol == PACIENTE:
        paciente_propio = get_object_or_404(Paciente, usuario=usuario, activo=True)
    if request.method == "POST":
        valores = request.POST.copy()
        if paciente_propio:
            valores["paciente"] = str(paciente_propio.pk)
            valores["estado"] = "programada"
            valores["duracion_minutos"] = "30"
        elif not valores.get("duracion_minutos"):
            valores["duracion_minutos"] = "30"
        form = CitaForm(valores, instance=cita)
        # Un paciente no puede enviar su propia selección de paciente/estado/duración.
        if form.is_valid():
            objeto = form.save(commit=False)
            if not cita and objeto.estado not in ("programada", "disponible"):
                form.add_error("estado", "Una cita nueva debe estar programada o disponible.")
            elif objeto.estado == "disponible" and objeto.paciente_id:
                form.add_error("estado", "Una cita disponible no puede tener un paciente.")
            else:
                try:
                    with transaction.atomic():
                        # Serializa operaciones en bases que soportan SELECT FOR UPDATE.
                        list(Consultorio.objects.select_for_update().filter(pk=objeto.consultorio_id))
                        list(Medico.objects.select_for_update().filter(pk=objeto.medico_id))
                        objeto.save()
                    messages.success(request, "Cita guardada correctamente.")
                    return redirect("citas_list")
                except (ValidationError, IntegrityError):
                    form.add_error(None, "Horario ocupado o datos incorrectos. Selecciona otra fecha y hora.")
        _render_errors(request, form)
    return render(request, "core/citas/form.html", {
        "cita": cita,
        "pacientes": [paciente_propio] if paciente_propio else Paciente.objects.filter(activo=True),
        "medicos": Medico.objects.filter(activo=True, usuario__activo=True),
        "consultorios": Consultorio.objects.filter(activo=True),
        "es_form_paciente": bool(paciente_propio),
        "fecha_minima": timezone.localdate().isoformat(),
        "estados": Cita.ESTADOS,
    })


@clinic_login_required(ADMIN, MEDADMIN, PACIENTE)
def cita_create(request):
    return _render_cita(request)


@clinic_login_required(ADMIN, MEDADMIN)
def cita_edit(request, pk):
    cita = get_object_or_404(Cita, pk=pk)
    return _render_cita(request, cita)


@clinic_login_required(ADMIN, MEDADMIN, PACIENTE)
def cita_delete(request, pk):
    usuario = usuario_actual(request)
    qs = Cita.objects.all() if usuario.rol in GESTORES else Cita.objects.filter(paciente__usuario=usuario)
    cita = get_object_or_404(qs, pk=pk)
    if request.method == "POST":
        if cita.estado == "atendida" or (usuario.rol == PACIENTE and cita.fecha < timezone.localdate()):
            messages.error(request, "No es posible cancelar una cita ya atendida o pasada.")
        else:
            cita.estado = "cancelada"
            cita.save(update_fields=["estado"])
            messages.success(request, "Cita cancelada. Su historial se conserva.")
        return redirect("citas_list")
    return render(request, "core/citas/delete.html", {"cita": cita})


@clinic_login_required(MEDICO)
@require_POST
def cita_estado(request, pk):
    usuario = usuario_actual(request)
    cita = get_object_or_404(Cita, pk=pk, medico__usuario=usuario)
    estado = request.POST.get("estado")
    if estado != "atendida" or cita.estado not in ("programada", "reprogramada"):
        return HttpResponseBadRequest("Transición de estado inválida.")
    if cita.fecha > timezone.localdate() or (cita.fecha == timezone.localdate() and cita.hora > timezone.localtime().time()):
        return HttpResponseBadRequest("Todavía no ha llegado la hora de esta atención.")
    cita.estado = estado
    cita.save(update_fields=["estado"])
    messages.success(request, "Estado de cita actualizado.")
    return redirect("cita_detail", pk=pk)


@clinic_login_required()
def perfil(request):
    usuario = usuario_actual(request)
    if request.method == "POST":
        correo = request.POST.get("correo_electronico", "").strip()
        clave_actual = request.POST.get("clave_actual", "")
        clave_nueva = request.POST.get("clave_nueva", "")
        if not usuario.check_password(clave_actual):
            messages.error(request, "La contraseña actual no es correcta.")
        else:
            from django.core.validators import validate_email
            try:
                if correo:
                    validate_email(correo)
                if clave_nueva:
                    validate_password(clave_nueva)
                usuario.correo_electronico = correo
                if clave_nueva:
                    usuario.set_password(clave_nueva)
                usuario.save()
                if clave_nueva:
                    request.session["clinic_sello"] = sello_sesion(usuario)
                    request._clinic_user_cache = usuario
                messages.success(request, "Perfil actualizado.")
                return redirect("perfil")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
    return render(request, "core/perfil.html", {"cuenta": usuario})


def recuperar_contrasenia(request):
    if request.method == "POST":
        correo = request.POST.get("correo", "").strip().lower()
        usuario = Usuario.objects.filter(correo_electronico__iexact=correo, activo=True).first() if correo else None
        clave = "recuperacion:" + str(request.META.get("REMOTE_ADDR", ""))
        intentos = cache.get(clave, 0)
        if intentos < 5:
            cache.set(clave, intentos + 1, 3600)
            if usuario:
                uid = urlsafe_base64_encode(force_bytes(usuario.pk))
                token = tokens.make_token(usuario)
                ruta = request.build_absolute_uri(f"/recuperar/{uid}/{token}/")
                send_mail("Restablecer contraseña de Sonrisa360", f"Abre este enlace para cambiar tu contraseña (válido por tiempo limitado): {ruta}", None, [usuario.correo_electronico], fail_silently=False)
        messages.info(request, "Si el correo está registrado, recibirás instrucciones para restablecer tu contraseña.")
        return redirect("login")
    return render(request, "core/recuperar.html")


def nueva_contrasenia(request, uid, token):
    try:
        usuario = Usuario.objects.filter(pk=force_str(urlsafe_base64_decode(uid)), activo=True).first()
    except (ValueError, TypeError, OverflowError):
        usuario = None
    if not usuario or not tokens.check_token(usuario, token):
        return render(request, "core/recuperar.html", {"enlace_invalido": True}, status=400)
    if request.method == "POST":
        try:
            clave = request.POST.get("contrasenia", "")
            validate_password(clave)
            usuario.set_password(clave)
            usuario.save(update_fields=["contrasenia"])
            messages.success(request, "Contraseña actualizada. Inicia sesión.")
            return redirect("login")
        except ValidationError as exc:
            for e in exc.messages:
                messages.error(request, e)
    return render(request, "core/nueva_contrasenia.html")


@clinic_login_required(ADMIN, MEDADMIN)
def cotizaciones_list(request):
    qs = Cotizacion.objects.select_related("cita__paciente", "cita__medico").order_by("-creada_en")
    return render(request, "core/cotizaciones/list.html", {"cotizaciones": qs})


@clinic_login_required(MEDICO, PACIENTE)
def mis_cotizaciones(request):
    u = usuario_actual(request)
    qs = Cotizacion.objects.select_related("cita__paciente", "cita__medico").order_by("-creada_en")
    if u.rol == MEDICO:
        qs = qs.filter(cita__medico__usuario=u)
    else:
        qs = qs.filter(cita__paciente__usuario=u).exclude(estado="borrador")
    return render(request, "core/cotizaciones/list.html", {"cotizaciones": qs})


@clinic_login_required()
def cotizacion_detail(request, pk):
    u = usuario_actual(request)
    qs = Cotizacion.objects.select_related("cita__paciente", "cita__medico")
    if u.rol == MEDICO:
        qs = qs.filter(cita__medico__usuario=u)
    elif u.rol == PACIENTE:
        qs = qs.filter(cita__paciente__usuario=u).exclude(estado="borrador")
    return render(request, "core/cotizaciones/detail.html", {"cotizacion": get_object_or_404(qs, pk=pk)})


@clinic_login_required(ADMIN, MEDADMIN)
def cotizacion_create(request):
    if request.method == "POST":
        form = CotizacionForm(request.POST)
        item_form = ItemCotizacionForm(request.POST)
        if form.is_valid() and item_form.is_valid():
            if form.cleaned_data["estado"] not in ("borrador", "enviada"):
                form.add_error("estado", "Una cotización nueva no puede estar aprobada ni rechazada.")
            if not form.cleaned_data["cita"].paciente_id:
                form.add_error("cita", "La cita debe tener paciente asignado.")
            if not form.errors:
                with transaction.atomic():
                    cotizacion = form.save()
                    item = item_form.save(commit=False)
                    item.cotizacion = cotizacion
                    item.save()
                messages.success(request, "Cotización registrada correctamente.")
                return redirect("cotizacion_detail", pk=cotizacion.pk)
        _render_errors(request, form, item_form)
    else:
        form = CotizacionForm()
        item_form = ItemCotizacionForm()
    return render(request, "core/cotizaciones/form.html", {"form": form, "item_form": item_form})


@clinic_login_required(ADMIN, MEDADMIN)
def cotizacion_item(request, pk):
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    if cotizacion.estado != "borrador":
        raise PermissionDenied("Los conceptos solo pueden modificarse en borrador.")
    form = ItemCotizacionForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            item = form.save(commit=False)
            item.cotizacion = cotizacion
            item.save()
            messages.success(request, "Concepto agregado.")
            return redirect("cotizacion_detail", pk=pk)
        _render_errors(request, form)
    return render(request, "core/cotizaciones/item.html", {"form": form, "cotizacion": cotizacion})


@clinic_login_required(ADMIN, MEDADMIN, MEDICO)
@require_POST
def cotizacion_estado(request, pk):
    usuario = usuario_actual(request)
    qs = Cotizacion.objects.all()
    if usuario.rol == MEDICO:
        qs = qs.filter(cita__medico__usuario=usuario)
    cotizacion = get_object_or_404(qs, pk=pk)
    nuevo_estado = request.POST.get("estado")
    if nuevo_estado not in ("enviada", "aprobada", "rechazada"):
        return HttpResponseBadRequest("Estado no permitido")
    if cotizacion.estado in ("aprobada", "rechazada"):
        raise PermissionDenied("La cotización ya está cerrada.")
    if cotizacion.estado == "borrador" and nuevo_estado != "enviada":
        return HttpResponseBadRequest("Primero debes enviar la cotización para revisión.")
    cotizacion.estado = nuevo_estado
    cotizacion.save(update_fields=["estado", "actualizada_en"])
    messages.success(request, "Estado de cotización actualizado.")
    return redirect("cotizacion_detail", pk=pk)


@clinic_login_required(ADMIN)
def horarios_medico(request, pk):
    medico = get_object_or_404(Medico, pk=pk)
    if request.method == "POST":
        form = HorarioForm(request.POST)
        if form.is_valid():
            horario = form.save(commit=False)
            horario.medico = medico
            try:
                horario.full_clean()
                horario.save()
                messages.success(request, "Horario agregado.")
                return redirect("horarios_medico", pk=pk)
            except ValidationError as e:
                messages.error(request, "; ".join(e.messages))
        _render_errors(request, form)
    else:
        form = HorarioForm()
    return render(request, "core/horarios.html", {"medico": medico, "horarios": medico.horarios.all(), "form": form})


@clinic_login_required(ADMIN)
@require_POST
def horario_delete(request, pk):
    horario = get_object_or_404(HorarioMedico, pk=pk)
    medico_id = horario.medico_id
    horario.delete()
    return redirect("horarios_medico", pk=medico_id)
