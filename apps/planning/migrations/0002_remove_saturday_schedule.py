"""Migration : suppression du WeeklySaturdaySchedule.

Le samedi est désormais un jour normal en mode OPTIONAL (pointage libre).
Plus de planification hebdomadaire individuelle.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='WeeklySaturdaySchedule',
        ),
        migrations.AlterField(
            model_name='dailyschedule',
            name='mode',
            field=models.CharField(
                choices=[
                    ('NOT_WORKED', 'Non travaillé'),
                    ('MANDATORY', 'Obligatoire'),
                    ('OPTIONAL', 'Optionnel (pointage libre)'),
                ],
                default='NOT_WORKED',
                max_length=20,
                verbose_name='Mode',
            ),
        ),
    ]
