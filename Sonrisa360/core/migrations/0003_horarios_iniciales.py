from datetime import time
from django.db import migrations


def configurar_horarios_default(apps, schema_editor):
    Medico = apps.get_model("core", "Medico")
    Horario = apps.get_model("core", "HorarioMedico")
    for medico in Medico.objects.all():
        if not Horario.objects.filter(medico_id=medico.pk).exists():
            for dia in range(5):
                Horario.objects.create(medico_id=medico.pk, dia_semana=dia, hora_inicio=time(8), hora_fin=time(18))


def revertir_sin_borrado(apps, schema_editor):
    # No se borran horarios: podrían haberse actualizado manualmente.
    pass


class Migration(migrations.Migration):
    dependencies = [("core", "0002_cotizacion_horariomedico_itemcotizacion_and_more")]
    operations = [migrations.RunPython(configurar_horarios_default, revertir_sin_borrado)]
