# Sonrisa360 — Versión mejorada del proyecto Django

**Base:** proyecto `django-clinica (2)version actual.zip` entregado por el equipo. Esta entrega de código **no incluye `db.sqlite3`**, datos de pacientes, contraseñas conocidas ni el entorno virtual anterior.

## Cambios implementados

- Inicio de sesión para **Admin, Médico administrador, Médico y Paciente**, con sesión revocable al cambiar contraseña o desactivar usuario y cierre por POST.
- Comprobación de rol desde el servidor: los pacientes solo consultan sus citas y cotizaciones; los médicos, sus citas y cotizaciones asignadas; gestores y administradores tienen funciones diferenciadas.
- Panel individual para médicos y pacientes, menú por rol y página de perfil para cambiar contraseña y configurar correo de recuperación.
- Alta y modificación de pacientes/médicos con validaciones, contraseñas cifradas y transacciones atómicas; documento como texto.
- Baja lógica de pacientes, médicos y consultorios, sin borrar el historial de citas; cancelaciones de cita sin eliminación física.
- Reglas para citas: fecha futura, verificación de profesional, consultorio, intervalos según duración, horario laboral configurable, estados coherentes y restricciones de BD para coincidencias exactas.
- Historial de cambios de fecha, hora y estado de las citas (no incluye autor del cambio; esta parte requiere una ampliación futura de auditoría).
- Cotizaciones con conceptos, totales calculados, estados y visibilidad por paciente/médico; sin procesamiento de pagos.
- Horarios semanales de médicos editables por administrador; datos existentes reciben turnos iniciales de lunes a viernes 08:00–18:00 que deben revisarse.
- Recuperación de contraseña por correo con token de una hora, sujeta a configurar SMTP real.
- Archivos de configuración por entorno y 20 pruebas automáticas de seguridad y reglas de negocio.

## Instalación nueva en Windows (PowerShell)

1. Extraer el ZIP en una carpeta cuyo nombre no tenga caracteres extraños.
2. Abrir esa carpeta en Visual Studio Code, junto a `manage.py`.
3. Instalar Python 3.12 o 3.13 y ejecutar:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py inicializar_catalogos
python manage.py crear_administrador
python manage.py check
python manage.py test core
python manage.py runserver
```

Abrir `http://127.0.0.1:8000/login/`. Ingresa con la cuenta administrativa creada. Desde la interfaz puedes crear pacientes y médicos, configurando un usuario y contraseña seguros para cada uno. Al registrar un médico, puedes asignar el rol **Médico** o **Médico administrador**.

> Si PowerShell no permite activar el entorno, utiliza directamente `.venv\Scripts\python.exe manage.py migrate` (y el resto de los comandos con esa ruta) o revisa las políticas locales de ejecución. No hace falta modificar las políticas de forma permanente.

## Actualización conservando la base de datos anterior

**Haz esto en una copia, no sobre el proyecto de trabajo.**

1. Cierra el servidor Django anterior.
2. Guarda una copia segura de la carpeta y de `db.sqlite3`, **en un lugar que no sea público**.
3. Extrae este proyecto actualizado en otra carpeta.
4. Copia `db.sqlite3` de la versión anterior a la nueva carpeta, junto a `manage.py`.
5. Instala el entorno virtual y las dependencias con los comandos anteriores.
6. Ejecuta **solo una vez** `python manage.py migrate`; las migraciones `0002` a `0006` conservan los registros existentes y agregan columnas, horarios, cotizaciones e historial.
7. Ejecuta `python manage.py check` y `python manage.py test core` (las pruebas usan una base temporal; **no deben cambiar tu base real**).
8. Inicia el servidor, comprueba una cuenta de cada rol y **cambia las contraseñas de prueba anteriores**, si siguen vigentes.
9. Verifica y ajusta los horarios creados inicialmente para cada odontólogo.

Si la copia anterior tiene datos duplicados o inconsistentes, una migración con restricciones nuevas podría detenerse. En ese caso, **no borres registros**; vuelve a la copia de seguridad y revisa las filas conflictivas antes de continuar.

## Cuentas y permisos

| Rol | Acceso |
|---|---|
| Admin | Gestión completa de personas, consultorios, citas, horarios y cotizaciones. |
| Médico administrador | Consulta pacientes, médicos y consultorios; gestiona citas y cotizaciones; no administra cuentas. |
| Médico | Su agenda, citas asignadas, estado de sus citas y cotizaciones relacionadas. |
| Paciente | Su panel, sus citas, agendamiento y cotizaciones no borrador. |

La pantalla de login NO contiene contraseñas de demostración. No existe registro público automático de pacientes: el administrador crea las cuentas y entrega las credenciales por un canal seguro.

## Recuperación de acceso

1. Usuario entra a **¿Olvidaste tu contraseña?** e introduce el correo configurado en **Mi perfil**.
2. Django genera un enlace temporal de restablecimiento.
3. En desarrollo, los correos se imprimen en la consola de `runserver`, y no se envían realmente. Para correo real, configura el servicio SMTP en variables de entorno: `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, `DJANGO_EMAIL_USE_TLS` y `DJANGO_DEFAULT_FROM_EMAIL`.
4. Recomendación futura: proceso de verificación de correo antes de permitir recuperación automática y gestión del envío con servicio confiable.

## Comprobaciones

```powershell
python manage.py check
python manage.py showmigrations core
python manage.py test core --verbosity 2
```

**Se ejecutaron 24 pruebas automatizadas** en el entorno de revisión con Django 5.2.6 y pasaron; al instalarlo en tu equipo, repítelas. Esto no reemplaza las pruebas de navegador ni una auditoría de seguridad.

## Preparar un despliegue público (NO basta con subir a Netlify Drop)

El backend Django necesita un servicio Python (WSGI/ASGI), una base de datos, almacenamiento, HTTPS y un servicio de correo. No publiques directamente `runserver`, SQLite ni el archivo `.env`.

- Configura `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` (aleatoria, secreta y de 50+ caracteres), `DJANGO_ALLOWED_HOSTS` (dominio real) y `DJANGO_CSRF_TRUSTED_ORIGINS` (por ejemplo `https://tu-dominio.com`).
- Ejecuta `python manage.py check --deploy` **con las variables de producción ya configuradas**, y corrige cualquier advertencia.
- Requiere un servidor HTTPS con Nginx/Caddy + Gunicorn u otro servidor WSGI adecuado. Configura `collectstatic` y la entrega de archivos estáticos desde un servidor confiable.
- Si está detrás de proxy HTTPS de confianza, se puede habilitar `DJANGO_TRUST_PROXY_HTTPS=1` tras validar que el proxy sobreescribe el encabezado `X-Forwarded-Proto`.
- **Para múltiples usuarios simultáneos usa PostgreSQL** y controla la concurrencia de agendamiento a nivel de transacciones de base de datos. SQLite es suficiente para desarrollo local, pero no garantiza exclusión completa ante múltiples procesos con horarios solapados.
- Agrega copias de seguridad probadas, registros y monitoreo, gestión de consentimiento/privacidad, políticas de conservación de datos y pruebas de penetración antes de usar datos clínicos reales.
- El login aquí preserva el modelo de usuario propio por compatibilidad con la base previa. Una migración futura al modelo de autenticación nativo de Django requiere un plan específico; las cuentas de `core.Usuario` **no son cuentas del panel `/admin/` de Django**.

## Limitaciones conocidas

- No hay verificación de titularidad de correo, notificaciones automáticas de citas ni pasarela de pagos.
- No hay autoservicio de registro de pacientes porque se necesita control de identidad y consentimiento.
- El historial de citas registra cambios de programación y estado, pero no identifica todavía al responsable ni almacena consentimiento.
- No es una aplicación certificada para producción médica ni prueba que cumpla requisitos legales de historias clínicas; requiere evaluación de privacidad y seguridad, así como despliegue externo.
- La galería de Netlify solo muestra los 12 mockups; no ejecuta este servidor Django.
