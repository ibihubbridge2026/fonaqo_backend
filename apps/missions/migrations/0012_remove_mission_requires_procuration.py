# Generated manually for FONACO roadmap

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0011_labor_material_withdrawal'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mission',
            name='requires_procuration',
        ),
    ]
