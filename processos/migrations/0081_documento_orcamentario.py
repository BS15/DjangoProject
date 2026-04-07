# Generated manually for DocumentoOrcamentario extraction from Processo

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import processos.models.segments._fluxo_models
import processos.validators
import simple_history.models


def backfill_documentos_orcamentarios(apps, schema_editor):
    Processo = apps.get_model("processos", "Processo")
    DocumentoOrcamentario = apps.get_model("processos", "DocumentoOrcamentario")

    batch = []
    for processo in Processo.objects.all().iterator():
        numero = getattr(processo, "n_nota_empenho", None)
        data = getattr(processo, "data_empenho", None)
        ano = getattr(processo, "ano_exercicio", None)

        if not any(v not in (None, "") for v in (numero, data, ano)):
            continue

        if data and not ano:
            ano = data.year

        batch.append(
            DocumentoOrcamentario(
                processo_id=processo.id,
                numero_nota_empenho=numero,
                data_empenho=data,
                ano_exercicio=ano,
            )
        )

    if batch:
        DocumentoOrcamentario.objects.bulk_create(batch, batch_size=500)


def reverse_backfill_documentos_orcamentarios(apps, schema_editor):
    DocumentoOrcamentario = apps.get_model("processos", "DocumentoOrcamentario")
    DocumentoOrcamentario.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("processos", "0080_contingencia_workflow_stages_and_contadora_review"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentoOrcamentario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("arquivo", models.FileField(blank=True, null=True, upload_to=processos.models.segments._fluxo_models.caminho_documento, validators=[processos.validators.validar_arquivo_seguro])),
                ("ordem", models.PositiveIntegerField(default=1, help_text="Ordem do arquivo")),
                ("numero_nota_empenho", models.CharField(blank=True, max_length=50, null=True)),
                ("data_empenho", models.DateField(blank=True, null=True)),
                (
                    "ano_exercicio",
                    models.IntegerField(
                        blank=True,
                        choices=[
                            (2020, 2020),
                            (2021, 2021),
                            (2022, 2022),
                            (2023, 2023),
                            (2024, 2024),
                            (2025, 2025),
                            (2026, 2026),
                            (2027, 2027),
                            (2028, 2028),
                            (2029, 2029),
                            (2030, 2030),
                            (2031, 2031),
                            (2032, 2032),
                            (2033, 2033),
                            (2034, 2034),
                        ],
                        null=True,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "processo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documentos_orcamentarios",
                        to="processos.processo",
                    ),
                ),
                (
                    "tipo",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="processos.tiposdedocumento"),
                ),
            ],
            options={"ordering": ["-data_empenho", "-id"]},
        ),
        migrations.CreateModel(
            name="HistoricalDocumentoOrcamentario",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                ("arquivo", models.TextField(blank=True, max_length=100, null=True)),
                ("ordem", models.PositiveIntegerField(default=1, help_text="Ordem do arquivo")),
                ("numero_nota_empenho", models.CharField(blank=True, max_length=50, null=True)),
                ("data_empenho", models.DateField(blank=True, null=True)),
                (
                    "ano_exercicio",
                    models.IntegerField(
                        blank=True,
                        choices=[
                            (2020, 2020),
                            (2021, 2021),
                            (2022, 2022),
                            (2023, 2023),
                            (2024, 2024),
                            (2025, 2025),
                            (2026, 2026),
                            (2027, 2027),
                            (2028, 2028),
                            (2029, 2029),
                            (2030, 2030),
                            (2031, 2031),
                            (2032, 2032),
                            (2033, 2033),
                            (2034, 2034),
                        ],
                        null=True,
                    ),
                ),
                ("criado_em", models.DateTimeField(blank=True, editable=False)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")], max_length=1)),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "processo",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="processos.processo",
                    ),
                ),
                (
                    "tipo",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="processos.tiposdedocumento",
                    ),
                ),
            ],
            options={
                "verbose_name": "historical documento orcamentario",
                "verbose_name_plural": "historical documento orcamentarios",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.RunPython(backfill_documentos_orcamentarios, reverse_backfill_documentos_orcamentarios),
    ]
