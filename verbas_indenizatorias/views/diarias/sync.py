"""Sincronização de diárias (integrações externas)."""

from commons.shared.csv_import_utils import build_csv_dict_reader
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from verbas_indenizatorias.models import Diaria

_COLUNAS_ID_DIARIA = ("DIARIA_ID", "ID_DIARIA", "ID", "PK")
_COLUNAS_NUMERO_SISCAC = (
    "NUMERO_SISCAC",
    "N_SISCAC",
    "NUMERO_DIARIA_SISCAC",
    "NUMERO_SISCAC_DIARIA",
)


def _primeiro_valor(row, candidates):
    for coluna in candidates:
        valor = (row.get(coluna) or "").strip()
        if valor:
            return valor
    return ""


def _sincronizar_numero_siscac(csv_file):
    resultados = {"criadas": 0, "atualizadas": 0, "erros": []}
    reader, erro = build_csv_dict_reader(
        csv_file,
        encodings=("utf-8-sig", "utf-8", "latin-1"),
        encoding_error_message="Não foi possível decodificar o CSV. Use UTF-8 ou Latin-1.",
    )
    if erro:
        resultados["erros"].append(erro)
        return resultados

    for line_num, row in enumerate(reader, start=2):
        diaria_id_raw = _primeiro_valor(row, _COLUNAS_ID_DIARIA)
        numero_siscac = _primeiro_valor(row, _COLUNAS_NUMERO_SISCAC)

        if not diaria_id_raw:
            resultados["erros"].append(
                f"Linha {line_num}: informe o identificador da diária ({', '.join(_COLUNAS_ID_DIARIA)})."
            )
            continue

        if not numero_siscac:
            resultados["erros"].append(
                f"Linha {line_num}: informe o número SISCAC ({', '.join(_COLUNAS_NUMERO_SISCAC)})."
            )
            continue

        try:
            diaria_id = int(diaria_id_raw)
            diaria = Diaria.objects.get(pk=diaria_id)
            if (diaria.numero_siscac or "") == numero_siscac:
                continue

            diaria.numero_siscac = numero_siscac
            diaria.save(update_fields=["numero_siscac"])
            resultados["atualizadas"] += 1
        except ValueError:
            resultados["erros"].append(f"Linha {line_num}: ID de diária inválido ('{diaria_id_raw}').")
        except Diaria.DoesNotExist:
            resultados["erros"].append(f"Linha {line_num}: diária ID {diaria_id_raw} não encontrada.")
        except Exception as exc:
            resultados["erros"].append(f"Linha {line_num}: erro ao sincronizar diária ID {diaria_id_raw}: {exc}")

    return resultados


@require_http_methods(["GET", "POST"])
@permission_required("pagamentos.pode_sincronizar_diarias_siscac", raise_exception=True)
def sincronizar_diarias(request):
    """Renderiza e processa a sincronização de números SISCAC de diárias via CSV."""
    if request.method == "GET":
        return render(request, "verbas/sincronizar_diarias.html", {})

    csv_file = request.FILES.get("siscac_csv")
    if not csv_file:
        messages.error(request, "Nenhum arquivo CSV foi enviado.")
        return redirect("sincronizar_diarias")

    resultados = _sincronizar_numero_siscac(csv_file)
    if resultados["atualizadas"]:
        messages.success(request, f"{resultados['atualizadas']} diária(s) sincronizada(s) com sucesso.")
    if resultados["erros"]:
        messages.warning(request, f"Sincronização concluída com {len(resultados['erros'])} erro(s).")

    return render(request, "verbas/sincronizar_diarias.html", {"resultados": resultados})


__all__ = ["sincronizar_diarias"]
