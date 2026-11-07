from django.contrib import admin
from .models import Usuario, Paciente, Medico, EspecialidadMedico, Consultorio, Cita, HorarioMedico, Cotizacion, ItemCotizacion, CitaHistorial


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ["usuario", "rol", "activo"]
    list_filter = ["rol", "activo"]
    search_fields = ["usuario"]
    readonly_fields = ["contrasenia"]
    # El alta de cuentas se hace desde Sonrisa360 o el comando seguro.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SinBorradoDirecto(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EspecialidadMedico)
class EspecialidadMedicoAdmin(admin.ModelAdmin):
    list_display = ["nombre_especialidad"]
    search_fields = ["nombre_especialidad"]


@admin.register(Paciente)
class PacienteAdmin(SinBorradoDirecto):
    list_display = ["nombre_completo", "documento", "telefono", "genero_paciente"]
    list_filter = ["genero_paciente"]
    search_fields = ["nombre_paciente", "apellido_paciente", "documento"]


@admin.register(Medico)
class MedicoAdmin(SinBorradoDirecto):
    list_display = ["nombre_completo", "especialidad", "telefono", "correo_electronico"]
    list_filter = ["especialidad", "genero_medico"]
    search_fields = ["nombre_medico", "apellido_medico", "correo_electronico"]


@admin.register(Consultorio)
class ConsultorioAdmin(SinBorradoDirecto):
    list_display = ["nombre", "ubicacion"]
    search_fields = ["nombre", "ubicacion"]


@admin.register(Cita)
class CitaAdmin(SinBorradoDirecto):
    list_display = ["paciente", "medico", "fecha", "hora", "estado", "consultorio"]
    list_filter = ["estado", "fecha", "medico__especialidad"]
    search_fields = ["paciente__nombre_paciente", "medico__nombre_medico"]
    date_hierarchy = "fecha"


@admin.register(HorarioMedico)
class HorarioMedicoAdmin(SinBorradoDirecto):
    list_display = ["medico", "dia_semana", "hora_inicio", "hora_fin", "activo"]


@admin.register(Cotizacion)
class CotizacionAdmin(SinBorradoDirecto):
    list_display = ["id", "cita", "estado", "creada_en"]


@admin.register(ItemCotizacion)
class ItemCotizacionAdmin(SinBorradoDirecto):
    list_display = ["cotizacion", "concepto", "cantidad", "valor_unitario"]


@admin.register(CitaHistorial)
class CitaHistorialAdmin(admin.ModelAdmin):
    list_display = ["cita", "creado_en", "estado_anterior", "estado_nuevo"]
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
