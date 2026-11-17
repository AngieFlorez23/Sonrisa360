from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Paciente, Medico, Consultorio, Cita, Cotizacion, ItemCotizacion, HorarioMedico, Usuario


class CuentaForm(forms.Form):
    usuario = forms.CharField(max_length=150)
    contrasenia = forms.CharField(required=False, widget=forms.PasswordInput)
    correo_electronico_usuario = forms.EmailField(required=False, label="Correo de recuperación")

    def __init__(self, *args, cuenta=None, nueva=False, **kwargs):
        self.cuenta = cuenta
        self.nueva = nueva
        super().__init__(*args, **kwargs)

    def clean_usuario(self):
        nombre = self.cleaned_data["usuario"].strip()
        existentes = Usuario.objects.filter(usuario__iexact=nombre)
        if self.cuenta:
            existentes = existentes.exclude(pk=self.cuenta.pk)
        if existentes.exists():
            raise ValidationError("Este nombre de usuario ya existe.")
        return nombre

    def clean_contrasenia(self):
        clave = self.cleaned_data["contrasenia"]
        if self.nueva and not clave:
            raise ValidationError("Debes establecer una contraseña.")
        if clave:
            validate_password(clave)
        return clave


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ["nombre_paciente", "apellido_paciente", "documento", "genero_paciente",
                  "fecha_nacimiento", "telefono", "direccion"]

    def clean_documento(self):
        documento = self.cleaned_data["documento"].strip()
        if not documento.isdigit() or len(documento) < 4:
            raise ValidationError("El documento debe tener al menos cuatro dígitos.")
        return documento

    def clean_fecha_nacimiento(self):
        from django.utils import timezone
        f = self.cleaned_data["fecha_nacimiento"]
        if f > timezone.localdate():
            raise ValidationError("La fecha de nacimiento no puede estar en el futuro.")
        return f


class MedicoForm(forms.ModelForm):
    class Meta:
        model = Medico
        fields = ["especialidad", "nombre_medico", "apellido_medico", "genero_medico",
                  "telefono", "correo_electronico"]


class ConsultorioForm(forms.ModelForm):
    class Meta:
        model = Consultorio
        fields = ["nombre", "ubicacion"]


class CitaForm(forms.ModelForm):
    class Meta:
        model = Cita
        fields = ["paciente", "medico", "consultorio", "fecha", "hora", "estado", "duracion_minutos"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["medico"].queryset = Medico.objects.filter(activo=True, usuario__activo=True)
        self.fields["consultorio"].queryset = Consultorio.objects.filter(activo=True)
        self.fields["paciente"].queryset = Paciente.objects.filter(activo=True, usuario__activo=True)


class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = ["cita", "descripcion", "estado"]


class ItemCotizacionForm(forms.ModelForm):
    class Meta:
        model = ItemCotizacion
        fields = ["concepto", "cantidad", "valor_unitario"]


class HorarioForm(forms.ModelForm):
    class Meta:
        model = HorarioMedico
        fields = ["dia_semana", "hora_inicio", "hora_fin", "activo"]


class RegistroPacienteForm(PacienteForm):
    """Registro público: crea únicamente cuentas de paciente.

    Reutiliza los controles de documento y fecha del formulario existente.
    """
    usuario = forms.CharField(label="Nombre de usuario", max_length=150)
    correo_electronico_usuario = forms.EmailField(label="Correo electrónico de recuperación")
    password1 = forms.CharField(label="Contraseña", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar contraseña", strip=False, widget=forms.PasswordInput)
    acepto_datos = forms.BooleanField(
        label="Entiendo que esta es una demostración académica y usaré datos ficticios"
    )

    class Meta(PacienteForm.Meta):
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean_usuario(self):
        nombre = self.cleaned_data["usuario"].strip()
        if Usuario.objects.filter(usuario__iexact=nombre).exists():
            raise ValidationError("Este nombre de usuario ya está registrado.")
        return nombre

    def clean_correo_electronico_usuario(self):
        correo = self.cleaned_data["correo_electronico_usuario"].strip().lower()
        if Usuario.objects.filter(correo_electronico__iexact=correo).exists():
            raise ValidationError("Este correo ya está registrado. Puedes recuperar tu contraseña.")
        return correo

    def clean(self):
        cleaned = super().clean()
        clave = cleaned.get("password1")
        confirmacion = cleaned.get("password2")
        if clave and confirmacion and clave != confirmacion:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if clave:
            try:
                validate_password(clave)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned
