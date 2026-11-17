from .auth import usuario_actual, ADMIN, MEDADMIN, MEDICO, PACIENTE


def clinic_usuario(request):
    u = usuario_actual(request)
    return {
        "clinic_usuario": u,
        "es_admin": bool(u and u.rol == ADMIN),
        "es_gestor": bool(u and u.rol in (ADMIN, MEDADMIN)),
        "es_medico": bool(u and u.rol == MEDICO),
        "es_paciente": bool(u and u.rol == PACIENTE),
    }
