from getpass import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from core.models import Usuario


class Command(BaseCommand):
    help = "Crea un administrador de Sonrisa360 sin contraseñas públicas ni de ejemplo."

    def handle(self, *args, **options):
        nombre = input("Nombre de usuario: ").strip()
        correo = input("Correo de recuperación (opcional): ").strip()
        if not nombre or Usuario.objects.filter(usuario__iexact=nombre).exists():
            raise CommandError("Nombre de usuario no disponible.")
        clave = getpass("Contraseña: ")
        if clave != getpass("Repite la contraseña: "):
            raise CommandError("Las contraseñas no coinciden.")
        try:
            validate_password(clave)
        except ValidationError as e:
            raise CommandError("; ".join(e.messages))
        cuenta = Usuario(usuario=nombre, rol="Admin", correo_electronico=correo)
        cuenta.set_password(clave)
        cuenta.save()
        self.stdout.write(self.style.SUCCESS("Administrador creado correctamente."))
