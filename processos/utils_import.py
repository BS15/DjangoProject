import csv
import io

from processos.models import CargosFuncoes, ContasBancarias, Credor, ContaFixa


def importar_credores_csv(csv_file):
    resultados = {'sucessos': 0, 'erros': []}
    raw = csv_file.read()
    try:
        decoded = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        decoded = raw.decode('latin-1')
    reader = csv.DictReader(io.StringIO(decoded))
    for row in reader:
        try:
            cpf_cnpj_limpo = (
                row['CPF_CNPJ']
                .replace('.', '')
                .replace('-', '')
                .replace('/', '')
                .replace(' ', '')
                .strip()
            )
            tipo = 'PF' if len(cpf_cnpj_limpo) == 11 else 'PJ'
            defaults = {'nome': row['NOME'].strip(), 'tipo': tipo}

            grupo_nome = row.get('GRUPO', '').strip()
            cargo_nome = row.get('CARGO_FUNCAO', '').strip()

            if grupo_nome:
                if cargo_nome:
                    cargo_obj, _ = CargosFuncoes.objects.get_or_create(
                        grupo=grupo_nome,
                        cargo_funcao=cargo_nome,
                    )
                    defaults['cargo_funcao'] = cargo_obj

            banco = row.get('BANCO', '').strip() or None
            agencia = row.get('AGENCIA', '').strip() or None
            conta_num = row.get('CONTA', '').strip() or None
            pix = row.get('PIX', '').strip() or None

            credor, _ = Credor.objects.get_or_create(
                cpf_cnpj=cpf_cnpj_limpo,
                defaults=defaults,
            )

            if banco or agencia or conta_num:
                conta_bancaria, _ = ContasBancarias.objects.get_or_create(
                    titular=credor,
                    banco=banco,
                    agencia=agencia,
                    conta=conta_num,
                )
                if credor.conta_id != conta_bancaria.pk:
                    credor.conta = conta_bancaria
                    credor.save(update_fields=['conta'])

            if pix and credor.chave_pix != pix:
                credor.chave_pix = pix
                credor.save(update_fields=['chave_pix'])

            resultados['sucessos'] += 1
        except Exception as e:
            resultados['erros'].append(f"Linha {reader.line_num}: {e}")
    return resultados


def importar_contas_fixas_csv(csv_file):
    resultados = {'sucessos': 0, 'erros': []}
    raw = csv_file.read()
    try:
        decoded = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        decoded = raw.decode('latin-1')
    reader = csv.DictReader(io.StringIO(decoded))
    for row in reader:
        try:
            nome_credor = row['NOME_CREDOR'].strip()
            credor = Credor.objects.filter(nome__iexact=nome_credor).first()
            if not credor:
                resultados['erros'].append(
                    f"Linha {reader.line_num}: Credor '{nome_credor}' não encontrado."
                )
                continue
            ContaFixa.objects.get_or_create(
                credor=credor,
                referencia=row['DETALHAMENTO'].strip(),
                defaults={
                    'dia_vencimento': int(row['DIA_VENCIMENTO']),
                    'ativa': True,
                },
            )
            resultados['sucessos'] += 1
        except ValueError as e:
            resultados['erros'].append(f"Linha {reader.line_num}: {e}")
        except Exception as e:
            resultados['erros'].append(f"Linha {reader.line_num}: {e}")
    return resultados

