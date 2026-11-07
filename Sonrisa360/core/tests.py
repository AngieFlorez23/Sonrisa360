from datetime import timedelta, time
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import Usuario, Paciente, Medico, EspecialidadMedico, Consultorio, Cita, HorarioMedico, Cotizacion, ItemCotizacion


def usuario(nombre, rol, clave="UnaClaveDePruebas123!"):
    u = Usuario(usuario=nombre, rol=rol)
    u.set_password(clave)
    u.save()
    return u


class SeguridadYFlujos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = usuario("admin", "Admin")
        cls.medadmin = usuario("medadmin", "Médico administrador")
        cls.usu_medico = usuario("medico", "Médico")
        cls.usu_medico2 = usuario("medico2", "Médico")
        cls.usu_paciente = usuario("paciente", "Paciente")
        cls.usu_paciente2 = usuario("paciente2", "Paciente")
        esp = EspecialidadMedico.objects.create(nombre_especialidad="General")
        cls.medico = Medico.objects.create(usuario=cls.usu_medico, especialidad=esp, nombre_medico="María", apellido_medico="Pérez", genero_medico="F", telefono="3001111111", correo_electronico="medico@example.org")
        cls.medico2 = Medico.objects.create(usuario=cls.usu_medico2, especialidad=esp, nombre_medico="Juan", apellido_medico="López", genero_medico="M", telefono="3002222222", correo_electronico="medico2@example.org")
        for medico in [cls.medico, cls.medico2]:
            for dia in range(5):
                HorarioMedico.objects.create(medico=medico, dia_semana=dia, hora_inicio=time(8), hora_fin=time(18))
        cls.paciente = Paciente.objects.create(usuario=cls.usu_paciente, nombre_paciente="Alicia", apellido_paciente="García", documento="10001", genero_paciente="F", fecha_nacimiento="1995-05-10", telefono="3012222222", direccion="Dirección simulada")
        cls.paciente2 = Paciente.objects.create(usuario=cls.usu_paciente2, nombre_paciente="Pablo", apellido_paciente="García", documento="10002", genero_paciente="M", fecha_nacimiento="1994-05-10", telefono="3013333333", direccion="Dirección simulada")
        cls.sala = Consultorio.objects.create(nombre="Consultorio 1", ubicacion="Planta 1")
        cls.sala2 = Consultorio.objects.create(nombre="Consultorio 2", ubicacion="Planta 1")
        fecha = timezone.localdate() + timedelta(days=1)
        while fecha.weekday() >= 5:
            fecha += timedelta(days=1)
        cls.fecha = fecha
        cls.cita = Cita.objects.create(paciente=cls.paciente, medico=cls.medico, consultorio=cls.sala, fecha=fecha, hora=time(9), estado="programada")

    def iniciar(self, nombre):
        return self.client.post(reverse("login"), {"username": nombre, "password": "UnaClaveDePruebas123!"})

    def test_login_por_los_cuatro_roles_y_panel(self):
        for nombre in ["admin", "medadmin", "medico", "paciente"]:
            self.client.post(reverse("logout")) if self.client.session.get("usuario_id") else None
            r = self.iniciar(nombre)
            self.assertEqual(r.status_code, 302, nombre)
            panel = self.client.get(reverse("dashboard"))
            self.assertEqual(panel.status_code, 200, nombre)
            self.assertContains(panel, nombre)

    def test_paciente_no_puede_consultar_ni_editar_otros_pacientes(self):
        self.iniciar("paciente")
        self.assertEqual(self.client.get(reverse("pacientes_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("paciente_edit", args=[self.paciente2.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("paciente_detail", args=[self.paciente2.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("cita_detail", args=[self.cita.pk])).status_code, 200)
        self.assertNotContains(self.client.get(reverse("dashboard")), "Gestión de pacientes")

    def test_paciente_no_puede_ver_cita_ajena(self):
        otra = Cita.objects.create(paciente=self.paciente2, medico=self.medico2, consultorio=self.sala2,
                                  fecha=self.fecha, hora=time(10), estado="programada")
        self.iniciar("paciente")
        self.assertEqual(self.client.get(reverse("cita_detail", args=[otra.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("citas_list")), self.paciente2.nombre_completo)

    def test_medico_ve_solo_sus_citas_y_no_administracion(self):
        self.iniciar("medico2")
        self.assertNotContains(self.client.get(reverse("citas_list")), self.paciente.nombre_completo)
        self.assertEqual(self.client.get(reverse("paciente_delete", args=[self.paciente.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("cita_edit", args=[self.cita.pk])).status_code, 403)

    def test_paciente_agenda_solo_para_si_mismo_ignora_datos_manipulados(self):
        self.iniciar("paciente")
        data = {"paciente": self.paciente2.pk, "medico": self.medico2.pk, "consultorio": self.sala2.pk,
                "fecha": self.fecha.isoformat(), "hora": "11:00", "estado": "atendida", "duracion_minutos": "180"}
        r = self.client.post(reverse("cita_create"), data)
        self.assertEqual(r.status_code, 302)
        nuevo = Cita.objects.get(medico=self.medico2, hora=time(11))
        self.assertEqual(nuevo.paciente_id, self.paciente.pk)
        self.assertEqual(nuevo.estado, "programada")
        self.assertEqual(nuevo.duracion_minutos, 30)

    def test_impedir_cruces_con_medico_y_con_consultorio(self):
        self.iniciar("admin")
        base = {"paciente": self.paciente2.pk, "medico": self.medico.pk,
                "consultorio": self.sala2.pk, "fecha": self.fecha.isoformat(),
                "hora": "09:15", "estado": "programada", "duracion_minutos": 30}
        r = self.client.post(reverse("cita_create"), base)
        self.assertEqual(r.status_code, 200)  # mismo médico, sala distinta pero solapamiento
        self.assertEqual(Cita.objects.count(), 1)
        base["medico"] = self.medico2.pk
        base["consultorio"] = self.sala.pk
        r = self.client.post(reverse("cita_create"), base)
        self.assertEqual(r.status_code, 200)  # otro médico, misma sala
        self.assertEqual(Cita.objects.count(), 1)

    def test_rechazar_fecha_pasada(self):
        self.iniciar("admin")
        data = {"paciente": self.paciente.pk, "medico": self.medico.pk, "consultorio": self.sala.pk,
                "fecha": (timezone.localdate() - timedelta(days=2)).isoformat(), "hora": "10:00",
                "estado": "programada", "duracion_minutos": 30}
        self.assertEqual(self.client.post(reverse("cita_create"), data).status_code, 200)
        self.assertEqual(Cita.objects.count(), 1)

    def test_cancelacion_conserva_historial_y_libera_horario(self):
        self.iniciar("paciente")
        self.assertEqual(self.client.post(reverse("cita_delete", args=[self.cita.pk])).status_code, 302)
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.estado, "cancelada")
        self.assertEqual(Cita.objects.count(), 1)
        nuevo = self.client.post(reverse("cita_create"), {
            "medico": self.medico.pk, "consultorio": self.sala.pk,
            "fecha": self.fecha.isoformat(), "hora": "09:00"})
        self.assertEqual(nuevo.status_code, 302)
        self.assertEqual(Cita.objects.count(), 2)

    def test_documento_duplicado_no_deja_cuenta_huerfana(self):
        self.iniciar("admin")
        data = {"usuario": "nuevoperfil", "contrasenia": "ClaveSeguraParaTest123!", "nombre_paciente": "Falso",
                "apellido_paciente": "Duplicado", "documento": self.paciente.documento, "genero_paciente": "F",
                "fecha_nacimiento": "2000-01-01", "telefono": "3222345678", "direccion": "Datos de prueba"}
        r = self.client.post(reverse("paciente_create"), data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Usuario.objects.filter(usuario="nuevoperfil").exists())
        self.assertEqual(Paciente.objects.count(), 2)

    def test_bloquear_eliminacion_definitiva_de_paciente(self):
        self.iniciar("admin")
        # Primero es necesario cancelar la cita futura.
        self.client.post(reverse("paciente_delete", args=[self.paciente.pk]))
        self.paciente.refresh_from_db()
        self.assertTrue(self.paciente.activo)
        self.client.post(reverse("cita_delete", args=[self.cita.pk]))
        self.client.post(reverse("paciente_delete", args=[self.paciente.pk]))
        self.paciente.refresh_from_db()
        self.assertFalse(self.paciente.activo)
        self.assertTrue(Cita.objects.filter(paciente=self.paciente).exists())
        self.client.post(reverse("logout"))
        self.assertEqual(self.iniciar("paciente").status_code, 200)

    def test_cotizacion_privada_y_total(self):
        cotizacion = Cotizacion.objects.create(cita=self.cita, estado="enviada")
        ItemCotizacion.objects.create(cotizacion=cotizacion, concepto="Limpieza", cantidad=2, valor_unitario=Decimal("40000.00"))
        self.assertEqual(cotizacion.total, Decimal("80000.00"))
        self.iniciar("paciente2")
        self.assertEqual(self.client.get(reverse("cotizacion_detail", args=[cotizacion.pk])).status_code, 404)
        self.client.post(reverse("logout"))
        self.iniciar("paciente")
        self.assertEqual(self.client.get(reverse("cotizacion_detail", args=[cotizacion.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("cotizacion_create")).status_code, 403)

    def test_usuario_no_puede_desactivar_medico_sin_permiso(self):
        self.iniciar("paciente")
        self.assertEqual(self.client.post(reverse("medico_delete", args=[self.medico.pk])).status_code, 403)
        self.medico.refresh_from_db()
        self.assertTrue(self.medico.activo)

    def test_medico_cambia_estado_solo_cita_propia(self):
        self.iniciar("medico2")
        self.assertEqual(self.client.post(reverse("cita_estado", args=[self.cita.pk]), {"estado": "atendida"}).status_code, 404)
        self.client.post(reverse("logout"))
        self.iniciar("medico")
        self.assertEqual(self.client.post(reverse("cita_estado", args=[self.cita.pk]), {"estado": "atendida"}).status_code, 400)
        # La cita debe haberse celebrado antes de marcarla atendida.
        Cita.objects.filter(pk=self.cita.pk).update(fecha=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.client.post(reverse("cita_estado", args=[self.cita.pk]), {"estado": "atendida"}).status_code, 302)
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.estado, "atendida")

    def test_logout_requiere_post(self):
        self.iniciar("paciente")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_gestor_medico_admin_no_puede_editar_médicos(self):
        self.iniciar("medadmin")
        self.assertEqual(self.client.get(reverse("pacientes_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("medicos_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("medico_edit", args=[self.medico.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("cotizaciones_list")).status_code, 200)
        self.assertNotContains(self.client.get(reverse("medicos_list")), 'href="/medicos/nuevo/"')

    def test_cotizacion_creacion_y_aprobacion_desde_gestor(self):
        self.iniciar("admin")
        r = self.client.post(reverse("cotizacion_create"), {
            "cita": self.cita.pk, "descripcion": "Tratamiento", "estado": "borrador",
            "concepto": "Limpieza", "cantidad": 2, "valor_unitario": "45000.00"})
        self.assertEqual(r.status_code, 302)
        cotizacion = Cotizacion.objects.get()
        self.assertEqual(cotizacion.total, Decimal("90000.00"))
        self.assertEqual(self.client.post(reverse("cotizacion_estado", args=[cotizacion.pk]), {"estado": "aprobada"}).status_code, 400)
        self.assertEqual(self.client.post(reverse("cotizacion_estado", args=[cotizacion.pk]), {"estado": "enviada"}).status_code, 302)
        self.client.post(reverse("logout"))
        self.iniciar("medico")
        self.assertEqual(self.client.post(reverse("cotizacion_estado", args=[cotizacion.pk]), {"estado": "aprobada"}).status_code, 302)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, "aprobada")

    def test_recuperacion_cambia_contrasenia_e_invalida_enlace(self):
        from django.core import mail
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from .views import tokens
        self.usu_paciente.correo_electronico = "persona@example.org"
        self.usu_paciente.save()
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            r = self.client.post(reverse("recuperar_contrasenia"), {"correo": "persona@example.org"})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(len(mail.outbox), 1)
            uid = urlsafe_base64_encode(force_bytes(self.usu_paciente.pk))
            token = tokens.make_token(self.usu_paciente)
            r = self.client.post(reverse("nueva_contrasenia", args=[uid, token]), {"contrasenia": "ClaveNuevaSegura123!"})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(self.client.get(reverse("nueva_contrasenia", args=[uid, token])).status_code, 400)
            self.assertEqual(self.client.post(reverse("login"), {"username": "paciente", "password": "ClaveNuevaSegura123!"}).status_code, 302)

    def test_turno_fuera_de_horario_rechazado(self):
        self.iniciar("admin")
        r = self.client.post(reverse("cita_create"), {
            "paciente": self.paciente2.pk, "medico": self.medico2.pk, "consultorio": self.sala2.pk,
            "fecha": self.fecha.isoformat(), "hora": "19:00", "estado": "programada", "duracion_minutos": 30})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Cita.objects.count(), 1)

    def test_conservar_historial_cuando_cancela(self):
        self.iniciar("admin")
        self.client.post(reverse("cita_delete", args=[self.cita.pk]))
        self.assertEqual(self.cita.movimientos.count(), 1)
        self.assertEqual(self.cita.movimientos.first().estado_anterior, "programada")
        self.assertEqual(self.cita.movimientos.first().estado_nuevo, "cancelada")

    def test_no_se_puede_acceder_a_sesion_con_clave_antigua(self):
        self.iniciar("paciente")
        self.usu_paciente.set_password("CambioSeguroOtraClave123!")
        self.usu_paciente.save()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_paciente_no_puede_tener_citas_simultaneas(self):
        self.iniciar("admin")
        r = self.client.post(reverse("cita_create"), {
            "paciente": self.paciente.pk, "medico": self.medico2.pk, "consultorio": self.sala2.pk,
            "fecha": self.fecha.isoformat(), "hora": "09:00", "estado": "programada", "duracion_minutos": 30})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Cita.objects.count(), 1)

    def test_cambio_medico_no_ignora_horario_laboral(self):
        self.iniciar("admin")
        # Cambiamos la agenda del segundo médico a horario vespertino.
        HorarioMedico.objects.filter(medico=self.medico2).delete()
        HorarioMedico.objects.create(medico=self.medico2, dia_semana=self.fecha.weekday(), hora_inicio=time(14), hora_fin=time(18))
        r = self.client.post(reverse("cita_edit", args=[self.cita.pk]), {
            "paciente": self.paciente.pk, "medico": self.medico2.pk, "consultorio": self.sala.pk,
            "fecha": self.fecha.isoformat(), "hora": "09:00", "estado": "programada", "duracion_minutos": 30})
        self.assertEqual(r.status_code, 200)
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.medico_id, self.medico.pk)

    def test_registrar_paciente_y_entrar_con_su_contrasenia(self):
        self.iniciar("admin")
        datos = {"usuario": "pacientenuevo", "contrasenia": "PacienteNuevoClave123!", "nombre_paciente": "Nuevo",
                 "apellido_paciente": "Paciente", "documento": "0007765", "genero_paciente": "O",
                 "fecha_nacimiento": "2001-06-02", "telefono": "3123456789", "direccion": "Dirección simulada"}
        self.assertEqual(self.client.post(reverse("paciente_create"), datos).status_code, 302)
        self.assertEqual(Paciente.objects.get(documento="0007765").usuario.rol, "Paciente")
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.post(reverse("login"), {"username": "pacientenuevo", "password": "PacienteNuevoClave123!"}).status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_crear_medico_administrador_y_horarios(self):
        self.iniciar("admin")
        esp = EspecialidadMedico.objects.first()
        datos = {"usuario": "doctoradministrativo", "rol": "Médico administrador", "contrasenia": "DoctorNuevoClave123!",
                 "especialidad": esp.pk, "nombre_medico": "Eva", "apellido_medico": "Sánchez",
                 "genero_medico": "F", "telefono": "3191234567", "correo_electronico": "eva@example.org"}
        self.assertEqual(self.client.post(reverse("medico_create"), datos).status_code, 302)
        medico = Medico.objects.get(usuario__usuario="doctoradministrativo")
        self.assertEqual(medico.usuario.rol, "Médico administrador")
        self.assertEqual(medico.horarios.count(), 5)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.post(reverse("login"), {"username": "doctoradministrativo", "password": "DoctorNuevoClave123!"}).status_code, 302)
        self.assertContains(self.client.get(reverse("dashboard")), "Panel del médico administrador")
