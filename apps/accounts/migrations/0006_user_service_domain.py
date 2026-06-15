from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_favoriteagent'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='service_domain',
            field=models.CharField(
                blank=True,
                max_length=255,
                verbose_name='domaine / compétences agent',
            ),
        ),
    ]
