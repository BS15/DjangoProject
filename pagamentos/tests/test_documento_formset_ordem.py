import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from pagamentos.forms import DocumentoFormSet


@pytest.mark.django_db
def test_documento_formset_ordem_vazia_nao_invalida_formset(processo_factory, tipo_documento_factory, pdf_bytes):
    processo = processo_factory()
    tipo_documento = tipo_documento_factory("BOLETO BANCARIO", tipo_pagamento=processo.tipo_pagamento)

    upload = SimpleUploadedFile("boleto.pdf", pdf_bytes, content_type="application/pdf")
    formset = DocumentoFormSet(
        data={
            "documento-TOTAL_FORMS": "1",
            "documento-INITIAL_FORMS": "0",
            "documento-MIN_NUM_FORMS": "0",
            "documento-MAX_NUM_FORMS": "1000",
            "documento-0-tipo": str(tipo_documento.id),
            "documento-0-ordem": "",
        },
        files={"documento-0-arquivo": upload},
        instance=processo,
        prefix="documento",
    )

    assert formset.is_valid(), formset.errors

    documentos = formset.save()
    assert len(documentos) == 1

    documento = documentos[0]
    documento.refresh_from_db()
    assert documento.ordem == 1
