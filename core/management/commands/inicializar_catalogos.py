from django.core.management.base import BaseCommand
from core.models import EspecialidadMedico, Consultorio


class Command(BaseCommand):
    help = "Crea especialidades y consultorios de ejemplo sin pacientes ni contraseñas."

    def handle(self, *args, **options):
        for nombre in ["Odontología General", "Ortodoncia", "Endodoncia", "Cirugía Oral"]:
            EspecialidadMedico.objects.get_or_create(nombre_especialidad=nombre)
        for nombre in ["Consultorio 1", "Consultorio 2"]:
            Consultorio.objects.get_or_create(nombre=nombre, defaults={"ubicacion": "Sede principal"})
        self.stdout.write(self.style.SUCCESS("Catálogos inicializados. Personaliza los consultorios para tu sede."))
