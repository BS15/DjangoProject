from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('processos', '0063_add_numero_siscac_to_diaria'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='diaria',
            name='numero_sequencial',
        ),
        migrations.RemoveField(
            model_name='historicaldiaria',
            name='numero_sequencial',
        ),
    ]
