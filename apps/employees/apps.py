from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.employees'
    label = 'employees'
    verbose_name = 'Employés'

    def ready(self):
        # Charge les signaux (modal anniversaire au login)
        from . import signals  # noqa: F401
