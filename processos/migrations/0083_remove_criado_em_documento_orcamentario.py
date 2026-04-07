from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("processos", "0082_rename_documentoprocesso_documentodepagamento"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="documentoorcamentario",
            name="criado_em",
        ),
        migrations.RemoveField(
            model_name="historicaldocumentoorcamentario",
            name="criado_em",
        ),
    ]
