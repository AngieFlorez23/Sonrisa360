from datetime import datetime, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password


class Usuario(models.Model):
    ROLES = [
        ("Médico", "Médico"),
        ("Paciente", "Paciente"),
        ("Admin", "Admin"),
        ("Médico administrador", "Médico administrador"),
    ]

    id_usuario = models.AutoField(primary_key=True)
    usuario = models.CharField(max_length=150, unique=True, verbose_name="Usuario")
    contrasenia = models.CharField(max_length=128, verbose_name="Contraseña")
    rol = models.CharField(max_length=30, choices=ROLES, verbose_name="Rol")
    activo = models.BooleanField(default=True)
    correo_electronico = models.EmailField(blank=True, verbose_name="Correo para recuperación")

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.usuario} ({self.rol})"

    def set_password(self, raw_password):
        """Encripta y guarda la contraseña"""
        self.contrasenia = make_password(raw_password)

    def check_password(self, raw_password):
        """Verifica la contraseña"""
        return check_password(raw_password, self.contrasenia)


class EspecialidadMedico(models.Model):
    id_especialidad = models.AutoField(primary_key=True)
    nombre_especialidad = models.CharField(max_length=100, verbose_name="Especialidad")

    class Meta:
        verbose_name = "Especialidad Médica"
        verbose_name_plural = "Especialidades Médicas"

    def __str__(self):
        return self.nombre_especialidad


class Paciente(models.Model):
    GENEROS = [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("O", "Otro"),
    ]

    id_paciente = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(Usuario, on_delete=models.PROTECT)
    nombre_paciente = models.CharField(max_length=100, verbose_name="Nombre")
    apellido_paciente = models.CharField(max_length=100, verbose_name="Apellido")
    documento = models.CharField(max_length=25, unique=True, verbose_name="Documento")
    genero_paciente = models.CharField(
        max_length=1, choices=GENEROS, verbose_name="Género"
    )
    fecha_nacimiento = models.DateField(verbose_name="Fecha de Nacimiento")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    direccion = models.CharField(max_length=200, verbose_name="Dirección")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"

    def __str__(self):
        return f"{self.nombre_paciente} {self.apellido_paciente}"

    @property
    def nombre_completo(self):
        return f"{self.nombre_paciente} {self.apellido_paciente}"


class Medico(models.Model):
    GENEROS = [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("O", "Otro"),
    ]

    id_medico = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(Usuario, on_delete=models.PROTECT)
    especialidad = models.ForeignKey(EspecialidadMedico, on_delete=models.PROTECT)
    nombre_medico = models.CharField(max_length=100, verbose_name="Nombre")
    apellido_medico = models.CharField(max_length=100, verbose_name="Apellido")
    genero_medico = models.CharField(
        max_length=1, choices=GENEROS, verbose_name="Género"
    )
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    correo_electronico = models.EmailField(verbose_name="Correo Electrónico")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"

    def __str__(self):
        return f"Dr. {self.nombre_medico} {self.apellido_medico} - {self.especialidad}"

    @property
    def nombre_completo(self):
        return f"Dr. {self.nombre_medico} {self.apellido_medico}"


class Consultorio(models.Model):
    id_consultorio = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Consultorio")
    ubicacion = models.CharField(max_length=200, verbose_name="Ubicación")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Consultorio"
        verbose_name_plural = "Consultorios"

    def __str__(self):
        return f"{self.nombre} - {self.ubicacion}"


class Cita(models.Model):
    ESTADOS = [
        ("programada", "Programada"),
        ("atendida", "Atendida"),
        ("cancelada", "Cancelada"),
        ("reprogramada", "Reprogramada"),
        ("disponible", "Disponible"),
    ]

    id_citas = models.AutoField(primary_key=True)
    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, null=True, blank=True
    )
    medico = models.ForeignKey(Medico, on_delete=models.PROTECT)
    consultorio = models.ForeignKey(Consultorio, on_delete=models.PROTECT)
    fecha = models.DateField(verbose_name="Fecha")
    hora = models.TimeField(verbose_name="Hora")
    duracion_minutos = models.PositiveSmallIntegerField(default=30)
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default="disponible", verbose_name="Estado"
    )

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        constraints = [
            models.UniqueConstraint(fields=["medico", "fecha", "hora"],
                                    condition=~Q(estado="cancelada"),
                                    name="cita_medico_hora_activa_unica"),
            models.UniqueConstraint(fields=["consultorio", "fecha", "hora"],
                                    condition=~Q(estado="cancelada"),
                                    name="cita_sala_hora_activa_unica"),
            models.UniqueConstraint(fields=["paciente", "fecha", "hora"],
                                    condition=Q(paciente__isnull=False) & ~Q(estado="cancelada"),
                                    name="cita_paciente_hora_activa_unica"),
        ]

    def __str__(self):
        paciente_nombre = (
            self.paciente.nombre_completo if self.paciente else "Sin asignar"
        )
        return f"{paciente_nombre} - Dr. {self.medico.nombre_completo} - {self.fecha} {self.hora}"

    def clean(self):
        super().clean()
        errores = {}
        if self.duracion_minutos is None or not 15 <= self.duracion_minutos <= 240:
            errores["duracion_minutos"] = "La duración debe estar entre 15 y 240 minutos."
        if self.estado == "disponible" and self.paciente_id:
            errores["estado"] = "Una cita disponible no puede tener paciente asignado."
        if self.estado in ("programada", "reprogramada", "atendida") and not self.paciente_id:
            errores["paciente"] = "Seleccione un paciente para esta cita."
        if self.fecha and self.hora:
            nueva_fecha = not self.pk
            original = None if nueva_fecha else type(self).objects.filter(pk=self.pk).values(
                "fecha", "hora", "medico_id", "consultorio_id", "duracion_minutos").first()
            ha_cambiado = nueva_fecha or (original and any([
                original["fecha"] != self.fecha, original["hora"] != self.hora,
                original["medico_id"] != self.medico_id, original["consultorio_id"] != self.consultorio_id,
                original["duracion_minutos"] != self.duracion_minutos]))
            if ha_cambiado:
                actual = timezone.localtime(timezone.now())
                if datetime.combine(self.fecha, self.hora) <= actual.replace(tzinfo=None):
                    errores["fecha"] = "No es posible programar una cita en el pasado."
            if self.estado == "atendida" and datetime.combine(self.fecha, self.hora) > timezone.localtime().replace(tzinfo=None):
                errores["estado"] = "No puede marcarse como atendida una cita que todavía no ocurre."
            if self.estado != "cancelada" and self.medico_id and self.consultorio_id:
                # El control de intervalos se ejecuta tanto al crear como al reprogramar.
                inicio = datetime.combine(self.fecha, self.hora)
                fin = inicio + timedelta(minutes=self.duracion_minutos or 30)
                otras = type(self).objects.filter(fecha=self.fecha).exclude(estado="cancelada")
                if self.pk:
                    otras = otras.exclude(pk=self.pk)
                condiciones = Q(medico_id=self.medico_id) | Q(consultorio_id=self.consultorio_id)
                if self.paciente_id:
                    condiciones |= Q(paciente_id=self.paciente_id)
                otras = otras.filter(condiciones)
                for otra in otras:
                    otro_inicio = datetime.combine(otra.fecha, otra.hora)
                    otro_fin = otro_inicio + timedelta(minutes=otra.duracion_minutos)
                    if inicio < otro_fin and otro_inicio < fin:
                        errores["hora"] = "Existe otra cita que se cruza con este médico o consultorio."
                        break
                if ha_cambiado and not errores.get("hora"):
                    # Sin horarios configurados se utiliza atención de lunes a viernes, 08:00–18:00.
                    dias = HorarioMedico.objects.filter(medico_id=self.medico_id, dia_semana=self.fecha.weekday(), activo=True)
                    # Si no existen horarios de este médico, no se bloquea su agenda antigua.
                    if HorarioMedico.objects.filter(medico_id=self.medico_id, activo=True).exists():
                        if not any(
                            inicio.time() >= h.hora_inicio and fin.date() == inicio.date() and fin.time() <= h.hora_fin
                            for h in dias
                        ):
                            errores["hora"] = "La cita está fuera del horario laboral del médico."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        anterior = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        self.full_clean()
        with transaction.atomic():
            resultado = super().save(*args, **kwargs)
            if anterior:
                campos = ("paciente_id", "medico_id", "consultorio_id", "fecha", "hora", "estado")
                if any(getattr(anterior, c) != getattr(self, c) for c in campos):
                    CitaHistorial.objects.create(
                        cita=self, estado_anterior=anterior.estado, estado_nuevo=self.estado,
                        fecha_anterior=anterior.fecha, hora_anterior=anterior.hora,
                        fecha_nueva=self.fecha, hora_nueva=self.hora,
                        descripcion="Actualización de programación o estado")
        return resultado


class CitaHistorial(models.Model):
    cita = models.ForeignKey(Cita, related_name="movimientos", on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)
    estado_anterior = models.CharField(max_length=20)
    estado_nuevo = models.CharField(max_length=20)
    fecha_anterior = models.DateField()
    hora_anterior = models.TimeField()
    fecha_nueva = models.DateField()
    hora_nueva = models.TimeField()
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("-creado_en",)


class HorarioMedico(models.Model):
    DIAS = [(0, "Lunes"), (1, "Martes"), (2, "Miércoles"), (3, "Jueves"),
            (4, "Viernes"), (5, "Sábado"), (6, "Domingo")]
    medico = models.ForeignKey(Medico, on_delete=models.PROTECT, related_name="horarios")
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("dia_semana", "hora_inicio")
        constraints = [models.UniqueConstraint(fields=["medico", "dia_semana", "hora_inicio"], name="horario_medico_unico")]

    def clean(self):
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError("La hora de finalización debe ser posterior al inicio.")
        if self.medico_id and self.hora_inicio and self.hora_fin and self.activo:
            otros = type(self).objects.filter(medico_id=self.medico_id, dia_semana=self.dia_semana, activo=True)
            if self.pk:
                otros = otros.exclude(pk=self.pk)
            for otro in otros:
                if self.hora_inicio < otro.hora_fin and otro.hora_inicio < self.hora_fin:
                    raise ValidationError("Este horario se cruza con otro turno del mismo médico.")

    def __str__(self):
        return f"{self.medico} - {self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fin}"


class Cotizacion(models.Model):
    ESTADOS = [("borrador", "Borrador"), ("enviada", "Enviada"),
               ("aprobada", "Aprobada"), ("rechazada", "Rechazada")]
    cita = models.ForeignKey(Cita, on_delete=models.PROTECT, related_name="cotizaciones")
    descripcion = models.TextField(blank=True)
    estado = models.CharField(max_length=15, choices=ESTADOS, default="borrador")
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Cotización {self.pk} - Cita {self.cita_id}"


class ItemCotizacion(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="items")
    concepto = models.CharField(max_length=200)
    cantidad = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.valor_unitario

    def clean(self):
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser positiva.")
        if self.valor_unitario is not None and self.valor_unitario < 0:
            raise ValidationError("El valor no puede ser negativo.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
