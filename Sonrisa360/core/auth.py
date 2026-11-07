"""Autenticación del Usuario heredado de Sonrisa360 sin migraciones destructivas.

NO confundir request.clinic_user con request.user de Django admin. El permiso
se comprueba en servidor en cada petición y nunca depende del menú mostrado.
"""
from functools import wraps
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.crypto import constant_time_compare, salted_hmac
from .models import Usuario

ADMIN = "Admin"
MEDADMIN = "Médico administrador"
MEDICO = "Médico"
PACIENTE = "Paciente"
GESTORES = {ADMIN, MEDADMIN}


def sello_sesion(usuario):
    return salted_hmac("sonrisa360.sesion", f"{usuario.pk}:{usuario.contrasenia}").hexdigest()


def usuario_actual(request):
    if hasattr(request, "_clinic_user_cache"):
        return request._clinic_user_cache
    pk = request.session.get("usuario_id")
    u = Usuario.objects.filter(pk=pk, activo=True).first() if pk else None
    if u and not constant_time_compare(request.session.get("clinic_sello", ""), sello_sesion(u)):
        u = None
    request._clinic_user_cache = u
    return u


def clinic_login_required(*roles):
    def decorador(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            u = usuario_actual(request)
            if u is None:
                request.session.flush()
                return redirect("login")
            if roles and u.rol not in roles:
                raise PermissionDenied("No tienes permisos para acceder a esta operación.")
            return view(request, *args, **kwargs)
        return wrapper
    return decorador


def rol_es(request, *roles):
    u = usuario_actual(request)
    return bool(u and u.rol in roles)
