"""Migration : modèle BroadcastMessage (messages diffusés RH → personnel)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BroadcastMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Titre')),
                ('body', models.TextField(
                    help_text='Texte du message. Les sauts de ligne sont préservés.',
                    verbose_name='Message',
                )),
                ('level', models.CharField(
                    choices=[('INFO', 'Information'), ('IMPORTANT', 'Important'), ('URGENT', 'Urgent')],
                    default='INFO', max_length=20, verbose_name='Niveau',
                )),
                ('is_active', models.BooleanField(
                    default=False,
                    help_text="Si coché, ce message s'affiche à tous les utilisateurs à la connexion. Les autres messages sont automatiquement désactivés.",
                    verbose_name='Diffusé',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('activated_at', models.DateTimeField(blank=True, null=True, verbose_name='Diffusé le')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='broadcast_messages',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
            ],
            options={
                'verbose_name': 'Message diffusé',
                'verbose_name_plural': 'Messages diffusés',
                'ordering': ['-created_at'],
            },
        ),
    ]
