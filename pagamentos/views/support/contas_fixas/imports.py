"""Import endpoints para contas fixas."""

import csv

from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def download_template_csv_contas(request):
    """Retorna template CSV de importação de contas fixas para download."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="template_contas_fixas.csv"'
    writer = csv.writer(response)
    writer.writerow(["CREDOR_CPF_CNPJ", "REFERENCIA", "DIA_VENCIMENTO", "DATA_INICIO", "ATIVA"])
    return response


__all__ = ["download_template_csv_contas"]
