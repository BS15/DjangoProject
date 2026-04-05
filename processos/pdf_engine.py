import io
import logging
import os
import textwrap
from datetime import date

from django.conf import settings
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from .utils.pdf_generation import merge_canvas_with_template
from .utils.text_helpers import format_brl_currency as _formatar_moeda

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared geometry / formatting helpers
# ---------------------------------------------------------------------------

# Proporção aproximada largura/tamanho-de-fonte para cálculo de quebra de linha (Helvetica).
_CHAR_WIDTH_RATIO = 0.55

# Altura reservada (em pontos) para os blocos de assinatura no rodapé.
_SIGNATURE_BLOCK_HEIGHT = 160

# Número máximo de entradas da trilha de auditoria exibidas no Parecer do Conselho.
_MAX_AUDIT_TRAIL_ENTRIES = 10

# Geometria do bloco de assinatura único (Termo de Autorização).
_AUTH_SIG_Y = 120
_AUTH_SIG_HALF_WIDTH = 130
_AUTH_SIG_DATE_OFFSET = 32

# Geometria dos blocos de assinatura triplos (Parecer do Conselho Fiscal).
_COUNCIL_SIG_Y = 110
_COUNCIL_SIG_WIDTH = 145

# Geometry for the PCD signature blocks.
_PCD_SIG_Y = 120
_PCD_SIG_HALF_WIDTH = 130

# Geometry for the SCD signature blocks.
_SCD_SIG_Y = 200
_SCD_SIG_LABEL_Y = 186

def _draw_wrapped_text(p, text, x, y, max_width, font_name="Helvetica", font_size=11, leading=16):
    """
    Desenha texto com quebra automática de linha no canvas ReportLab.
    Retorna a posição Y após o último texto desenhado.
    """
    if not text:
        return y
    p.setFont(font_name, font_size)
    chars_per_line = max(1, int(max_width / (font_size * _CHAR_WIDTH_RATIO)))
    lines = textwrap.wrap(str(text), width=chars_per_line)
    if not lines:
        lines = [str(text)]
    for line in lines:
        p.drawString(x, y, line)
        y -= leading
    return y


def _contar_paginas_documentos(processo):
    """
    Conta o número total de documentos e páginas nos DocumentoProcesso em PDF.
    Retorna uma tupla (total_documentos, total_paginas).
    """
    total_docs = 0
    total_pages = 0

    for doc in processo.documentos.all():
        total_docs += 1
        try:
            with doc.arquivo.open('rb') as f:
                reader = PdfReader(f)
                total_pages += len(reader.pages)
        except Exception:
            pass

    return total_docs, total_pages


class BasePDFDocument:
    """
    Base class for PDF document generation using the Strategy Pattern.

    Subclasses override ``draw_content`` to render their specific document
    layout onto ``self.canvas``.  ``generate`` then merges the result with
    the organisation letterhead and returns the final PDF bytes.
    """

    def __init__(self, obj, letterhead_path=None, **kwargs):
        self.obj = obj  # The database instance (Processo, Diaria, etc.)
        self.packet = io.BytesIO()
        self.canvas = canvas.Canvas(self.packet, pagesize=A4)
        self.page_width, self.page_height = A4
        self.letterhead_path = letterhead_path or getattr(settings, 'CRECI_LETTERHEAD_PATH', None)
        self.kwargs = kwargs

    def draw_content(self):
        """To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement draw_content()")

    def generate(self):
        """
        Renders the document content, merges it with the letterhead template
        and returns the final PDF as bytes.
        """
        # 1. Draw specific content
        self.draw_content()
        self.canvas.save()
        template_path = None
        if self.letterhead_path:
            template_path = os.path.join(settings.BASE_DIR, self.letterhead_path)
            if not os.path.exists(template_path):
                logger.warning(
                    "Letterhead file not found at '%s'. Generating PDF without letterhead.",
                    template_path,
                )
                template_path = None

        merged_packet = merge_canvas_with_template(self.packet, template_path)
        return merged_packet.getvalue()


class TermoContabilizacaoDocument(BasePDFDocument):
    """Generates the 'Termo de Contabilização' PDF for a given Processo."""

    def draw_content(self):
        processo = self.obj
        c = self.canvas
        page_width = self.page_width

        # --- Header ---
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 620, "TERMO DE CONTABILIZAÇÃO")

        # --- Process Details ---
        c.setFont("Helvetica", 11)
        line_height = 20
        y = 550
        credor_nome = processo.credor.nome if processo.credor else "N/A"
        details = [
            f"Processo Nº: {processo.id}",
            f"Nota de Empenho: {processo.n_nota_empenho or 'N/A'}",
            f"Credor: {credor_nome}",
            f"Valor Consolidado: R$ {processo.valor_liquido}",
        ]
        for line in details:
            c.drawString(72, y, line)
            y -= line_height

        # --- Declaration Text ---
        declaration = (
            "Certifico que a despesa referente ao Processo acima identificado foi devidamente "
            "registrada e contabilizada no sistema financeiro nesta data, em estrita conformidade "
            "com as normas contábeis e a legislação vigente."
        )
        c.setFont("Helvetica", 11)
        wrapped_lines = textwrap.wrap(declaration, width=85)
        y = 430
        for line in wrapped_lines:
            c.drawString(72, y, line)
            y -= line_height

        # --- Signature Block ---
        sig_x = page_width / 2
        c.line(sig_x - 120, 220, sig_x + 120, 220)
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 205, "Assinatura do(a) Contador(a)")
        c.drawCentredString(sig_x, 180, "Data da Contabilização: _____ / _____ / _________")


class TermoAtesteDocument(BasePDFDocument):
    """Generates the 'Termo de Liquidação e Ateste' PDF for a given DocumentoFiscal."""

    def draw_content(self):
        documento_fiscal = self.obj
        c = self.canvas
        page_width = self.page_width

        # --- Header ---
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 620, "TERMO DE LIQUIDAÇÃO E ATESTE")

        # --- Invoice Details ---
        c.setFont("Helvetica", 11)
        line_height = 20
        y = 550

        processo_id = (
            documento_fiscal.processo.id if documento_fiscal.processo else "N/A"
        )
        fornecedor = (
            documento_fiscal.processo.credor.nome
            if documento_fiscal.processo and documento_fiscal.processo.credor
            else "N/A"
        )
        details = [
            f"Processo Nº: {processo_id}",
            f"Documento Fiscal / Nota Nº: {documento_fiscal.numero_nota_fiscal}",
            f"Fornecedor: {fornecedor}",
            f"Valor do Documento: R$ {documento_fiscal.valor_bruto}",
        ]
        for line in details:
            c.drawString(72, y, line)
            y -= line_height

        # --- Declaration Text ---
        declaration = (
            "Atesto, para os devidos fins e sob as penas da lei, que os serviços referenciados "
            "no documento fiscal supra foram efetivamente prestados, ou os materiais entregues, "
            "de forma satisfatória e de acordo com as especificações contratuais exigidas."
        )
        c.setFont("Helvetica", 11)
        wrapped_lines = textwrap.wrap(declaration, width=85)
        y = 430
        for line in wrapped_lines:
            c.drawString(72, y, line)
            y -= line_height

        # --- Signature Block ---
        sig_x = page_width / 2
        if documento_fiscal.fiscal_contrato:
            fiscal_name = documento_fiscal.fiscal_contrato.get_full_name()
        else:
            fiscal_name = "Fiscal Não Atribuído"
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 235, fiscal_name)
        c.line(sig_x - 120, 220, sig_x + 120, 220)
        c.drawCentredString(sig_x, 205, "Fiscal do Contrato")
        c.drawCentredString(sig_x, 180, "Local e Data: Florianópolis, _____ / _____ / _________")


class AutorizacaoDocument(BasePDFDocument):
    """Generates the 'Termo de Autorização de Pagamento' PDF for a given Processo."""

    def draw_content(self):
        processo = self.obj
        c = self.canvas
        width = self.page_width
        height = self.page_height

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right

        y = height - 160

        # --- CABEÇALHO ---
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2.0, y, "TERMO DE AUTORIZAÇÃO DE PAGAMENTO")
        y -= 18
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(width / 2.0, y, f"PROCESSO Nº {processo.id}")
        y -= 30

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 20

        # --- DADOS DO CREDOR ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "DADOS DO CREDOR:")
        y -= 16
        c.setFont("Helvetica", 11)

        nome_credor = str(processo.credor.nome) if processo.credor and processo.credor.nome else "Não informado"
        cpf_cnpj = str(processo.credor.cpf_cnpj) if processo.credor and processo.credor.cpf_cnpj else "Não informado"

        c.drawString(margin_left, y, f"Nome / Razão Social:  {nome_credor}")
        y -= 16
        c.drawString(margin_left, y, f"CPF / CNPJ:           {cpf_cnpj}")
        y -= 24

        # --- COMPOSIÇÃO DO VALOR ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "COMPOSIÇÃO DO VALOR:")
        y -= 16
        c.setFont("Helvetica", 11)

        valor_bruto = processo.valor_bruto or 0
        valor_liquido = processo.valor_liquido or 0
        total_retencoes = valor_bruto - valor_liquido

        c.drawString(margin_left, y, f"Valor Bruto:                    {_formatar_moeda(valor_bruto)}")
        y -= 16
        c.drawString(margin_left, y, f"Total de Retenções (Impostos):  {_formatar_moeda(total_retencoes)}")
        y -= 16
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, f"Valor Líquido a Pagar:          {_formatar_moeda(valor_liquido)}")
        y -= 24

        # --- DADOS BANCÁRIOS DO CREDOR ---
        conta_credor = processo.credor.conta if processo.credor else None
        if conta_credor:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(margin_left, y, "DADOS BANCÁRIOS DO CREDOR:")
            y -= 16
            c.setFont("Helvetica", 11)
            c.drawString(margin_left, y, f"Banco:    {conta_credor.banco or 'Não informado'}")
            y -= 16
            c.drawString(margin_left, y, f"Agência:  {conta_credor.agencia or 'Não informado'}")
            y -= 16
            c.drawString(margin_left, y, f"Conta:    {conta_credor.conta or 'Não informado'}")
            y -= 24

        # --- DETALHAMENTO ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "DETALHAMENTO / JUSTIFICATIVA:")
        y -= 16
        detalhamento = processo.detalhamento or "Não informado."
        y = _draw_wrapped_text(c, detalhamento, margin_left, y, text_width, font_name="Helvetica", font_size=11)
        y -= 20

        # --- BOILERPLATE LEGAL ---
        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 16

        boilerplate = (
            "Autorizo, nos termos da legislação vigente, o pagamento da despesa acima especificada, "
            "face à regular liquidação do processo."
        )
        _draw_wrapped_text(c, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

        # --- BLOCO DE ASSINATURA ---
        sig_x = width / 2.0
        c.setFont("Helvetica", 10)
        c.drawCentredString(sig_x, _AUTH_SIG_Y + _AUTH_SIG_DATE_OFFSET, "Local e Data: _____________________________, _____ / _____ / _________")
        c.line(sig_x - _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y, sig_x + _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y)
        c.drawCentredString(sig_x, _AUTH_SIG_Y - 14, "Ordenador(a) de Despesa")


class PCDDocument(BasePDFDocument):
    """Generates the 'Proposta de Concessão de Diárias (PCD)' PDF for a given Diaria."""

    def draw_content(self):
        diaria = self.obj
        c = self.canvas
        width = self.page_width
        height = self.page_height

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right

        y = height - 160

        # --- CABEÇALHO ---
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2.0, y, "PROPOSTA DE CONCESSÃO DE DIÁRIAS (PCD)")
        y -= 18
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(width / 2.0, y, f"Nº {diaria.numero_siscac}")
        y -= 16
        c.setFont("Helvetica", 10)
        c.drawCentredString(width / 2.0, y, f"Tipo: {diaria.get_tipo_solicitacao_display()}")
        y -= 28

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 20

        # --- DADOS DO BENEFICIÁRIO ---
        nome = str(diaria.beneficiario.nome) if diaria.beneficiario and diaria.beneficiario.nome else "Não informado"
        cpf = str(diaria.beneficiario.cpf_cnpj) if diaria.beneficiario and diaria.beneficiario.cpf_cnpj else "Não informado"
        cargo = str(diaria.beneficiario.cargo_funcao) if diaria.beneficiario and diaria.beneficiario.cargo_funcao else "Não informado"

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "DADOS DO BENEFICIÁRIO:")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(margin_left, y, f"Nome:              {nome}")
        y -= 16
        c.drawString(margin_left, y, f"CPF:               {cpf}")
        y -= 16
        c.drawString(margin_left, y, f"Cargo / Função:    {cargo}")
        y -= 24

        # --- DADOS DO PROPONENTE ---
        if diaria.proponente:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(margin_left, y, "PROPONENTE:")
            y -= 16
            c.setFont("Helvetica", 11)
            nome_p = diaria.proponente.get_full_name() or diaria.proponente.username
            email_p = diaria.proponente.email or "Não informado"
            cargo_p = "Não informado"  # Proponent position not stored on the User model
            c.drawString(margin_left, y, f"Nome:              {nome_p}")
            y -= 16
            c.drawString(margin_left, y, f"E-mail:            {email_p}")
            y -= 16
            c.drawString(margin_left, y, f"Cargo / Função:    {cargo_p}")
            y -= 24

        # --- DADOS DA VIAGEM ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "DADOS DA VIAGEM:")
        y -= 16
        c.setFont("Helvetica", 11)

        data_saida = diaria.data_saida.strftime('%d/%m/%Y') if diaria.data_saida else "Não informado"
        data_retorno = diaria.data_retorno.strftime('%d/%m/%Y') if diaria.data_retorno else "Não informado"

        c.drawString(margin_left, y, f"Data de Saída:           {data_saida}")
        y -= 16
        c.drawString(margin_left, y, f"Data de Retorno:         {data_retorno}")
        y -= 16
        c.drawString(margin_left, y, f"Cidade de Origem:        {diaria.cidade_origem or 'Não informado'}")
        y -= 16
        c.drawString(margin_left, y, f"Cidade(s) de Destino:    {diaria.cidade_destino or 'Não informado'}")
        y -= 16
        if diaria.meio_de_transporte:
            c.drawString(margin_left, y, f"Meio de Transporte:      {diaria.meio_de_transporte}")
            y -= 16
        y -= 8

        # --- OBJETIVO DA VIAGEM ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "OBJETIVO DA VIAGEM:")
        y -= 16
        y = _draw_wrapped_text(c, diaria.objetivo or "Não informado.", margin_left, y, text_width,
                               font_name="Helvetica", font_size=11)
        y -= 20

        # --- VALORES ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "VALORES:")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(margin_left, y, f"Quantidade de Diárias:   {diaria.quantidade_diarias}")
        y -= 16
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, f"Valor Total:             {_formatar_moeda(diaria.valor_total)}")
        y -= 28

        # --- BOILERPLATE LEGAL ---
        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 14
        boilerplate = (
            "Proposta de concessão de diárias elaborada nos termos da legislação e regulamento interno vigentes, "
            "para fins de autorização pelo Ordenador de Despesas."
        )
        _draw_wrapped_text(c, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

        # --- BLOCOS DE ASSINATURA ---
        sig_left_x = margin_left + _PCD_SIG_HALF_WIDTH
        sig_right_x = width - margin_right - _PCD_SIG_HALF_WIDTH

        c.setFont("Helvetica", 9)

        # Beneficiário (left) — pre-filled identification
        c.drawCentredString(sig_left_x, _PCD_SIG_Y + 38, nome)
        c.drawCentredString(sig_left_x, _PCD_SIG_Y + 26, f"CPF: {cpf}")
        c.drawCentredString(sig_left_x, _PCD_SIG_Y + 14, cargo)
        c.line(sig_left_x - _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y,
               sig_left_x + _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y)
        c.drawCentredString(sig_left_x, _PCD_SIG_Y - 12, "Assinatura do(a) Beneficiário(a)")

        # Ordenador de Despesa (right)
        c.drawCentredString(sig_right_x, _PCD_SIG_Y + 14,
                            "Local e Data: _____ / _____ / _________")
        c.line(sig_right_x - _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y,
               sig_right_x + _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y)
        c.drawCentredString(sig_right_x, _PCD_SIG_Y - 12, "Ordenador(a) de Despesa")


class SCDDocument(BasePDFDocument):
    """Generates the 'Solicitação de Concessão de Diárias (SCD)' PDF for a given Diaria."""

    def draw_content(self):
        diaria = self.obj
        c = self.canvas
        width = self.page_width

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right

        # --- CABEÇALHO ---
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2.0, 620, "SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS - SCD")

        # --- DETALHES DO PROCESSO ---
        c.setFont("Helvetica", 11)
        y = 550

        siscac = diaria.numero_siscac or 'N/A'
        nome_benef = diaria.beneficiario.nome if diaria.beneficiario else 'N/A'
        cpf_benef = diaria.beneficiario.cpf_cnpj if diaria.beneficiario else 'N/A'
        proponente = diaria.proponente.get_full_name() if diaria.proponente else 'N/A'
        data_saida = diaria.data_saida.strftime('%d/%m/%Y') if diaria.data_saida else 'N/A'
        data_retorno = diaria.data_retorno.strftime('%d/%m/%Y') if diaria.data_retorno else 'N/A'
        transporte = diaria.meio_de_transporte.meio_de_transporte if diaria.meio_de_transporte else 'N/A'

        fields = [
            f"Nº SISCAC: {siscac}",
            f"Beneficiário: {nome_benef} - CPF: {cpf_benef}",
            f"Proponente: {proponente}",
            f"Período: {data_saida} a {data_retorno}",
            f"Trajeto: {diaria.cidade_origem} para {diaria.cidade_destino}",
            f"Transporte: {transporte}",
        ]
        for field in fields:
            c.drawString(margin_left, y, field)
            y -= 20

        # --- OBJETIVO ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, 430, "Objetivo:")
        _draw_wrapped_text(c, diaria.objetivo or 'N/A', margin_left, 410, text_width,
                           font_name="Helvetica", font_size=11)

        # --- CÁLCULO ---
        c.setFont("Helvetica", 11)
        c.drawString(
            margin_left, 380,
            f"Cálculo: {diaria.quantidade_diarias} diárias - Total Estimado: {_formatar_moeda(diaria.valor_total)}",
        )

        # --- BLOCOS DE ASSINATURA ---
        sig_left_x = margin_left + _PCD_SIG_HALF_WIDTH
        sig_right_x = width - margin_right - _PCD_SIG_HALF_WIDTH

        c.setFont("Helvetica", 10)
        c.line(sig_left_x - _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y,
               sig_left_x + _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y)
        c.drawCentredString(sig_left_x, _SCD_SIG_LABEL_Y, "Assinatura do Beneficiário")

        c.line(sig_right_x - _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y,
               sig_right_x + _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y)
        c.drawCentredString(sig_right_x, _SCD_SIG_LABEL_Y, "Assinatura do Proponente")


class ConselhoFiscalDocument(BasePDFDocument):
    """Generates the 'Parecer do Conselho Fiscal' PDF for a given Processo.

    Accepts an optional ``numero_reuniao`` keyword argument (via ``**kwargs``)
    to display the meeting number in the document header, e.g.:
        gerar_documento_pdf('conselho_fiscal', processo, numero_reuniao=5)
    """

    def draw_content(self):
        processo = self.obj
        c = self.canvas
        width = self.page_width
        height = self.page_height

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right
        # Limite inferior para conteúdo (acima dos blocos de assinatura)
        y_min = _SIGNATURE_BLOCK_HEIGHT

        y = height - 160

        # --- CABEÇALHO ---
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2.0, y, "PARECER DE AUDITORIA - CONSELHO FISCAL")
        y -= 18
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(width / 2.0, y, f"PROCESSO Nº {processo.id}")
        y -= 28

        numero_reuniao = self.kwargs.get('numero_reuniao')
        if numero_reuniao:
            c.setFont("Helvetica", 10)
            c.drawCentredString(
                width / 2.0, y,
                f"Processo aprovado na {numero_reuniao}ª Reunião do Conselho Fiscal"
            )
            y -= 18

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 18

        # --- INTEGRIDADE DOCUMENTAL ---
        total_docs, total_pages = _contar_paginas_documentos(processo)

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "INTEGRIDADE DOCUMENTAL:")
        y -= 16

        integridade_texto = (
            f"O processo é composto por {total_docs} documento(s) anexo(s) "
            f"totalizando {total_pages} página(s)."
        )
        y = _draw_wrapped_text(c, integridade_texto, margin_left, y, text_width, font_name="Helvetica", font_size=11)
        y -= 20

        # --- TRILHA DE AUDITORIA ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "TRILHA DE AUDITORIA (TRANSIÇÕES DE STATUS):")
        y -= 16

        history_records = list(processo.history.all().order_by('history_date'))
        log_lines = []
        for i, record in enumerate(history_records):
            prev_status_id = history_records[i - 1].status_id if i > 0 else None
            if record.history_type == '+' or (record.history_type == '~' and record.status_id != prev_status_id):
                try:
                    if record.history_user:
                        user_str = record.history_user.get_full_name() or record.history_user.username
                    else:
                        user_str = "Sistema"
                    date_str = record.history_date.strftime('%d/%m/%Y às %H:%M')
                    if record.history_type == '+':
                        log_lines.append(f"• Processo criado em {date_str} por {user_str}")
                    else:
                        status_str = str(record.status) if record.status else "Status atualizado"
                        log_lines.append(f"• {status_str} em {date_str} por {user_str}")
                except Exception:
                    pass

        if log_lines:
            for line in log_lines[:_MAX_AUDIT_TRAIL_ENTRIES]:
                if y > y_min:
                    y = _draw_wrapped_text(
                        c, line, margin_left, y, text_width,
                        font_name="Helvetica", font_size=10, leading=14,
                    )
        else:
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(margin_left, y, "Nenhuma transição de status registrada.")
            y -= 14

        y -= 16

        # --- CONTINGÊNCIAS ---
        if y > y_min:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(margin_left, y, "CONTINGÊNCIAS E RETIFICAÇÕES EXCEPCIONAIS:")
            y -= 16

            contingencias = processo.contingencias.all().select_related(
                'solicitante', 'aprovado_por_supervisor', 'aprovado_por_ordenador', 'aprovado_por_conselho'
            )

            if contingencias.exists():
                for cont in contingencias:
                    if y <= y_min:
                        break
                    solicitante_str = cont.solicitante.get_full_name() or cont.solicitante.username
                    data_str = cont.data_solicitacao.strftime('%d/%m/%Y')
                    status_display = cont.get_status_display()

                    cont_header = (
                        f"• Contingência #{cont.pk} [{status_display}] — "
                        f"Solicitada em {data_str} por {solicitante_str}"
                    )
                    y = _draw_wrapped_text(
                        c, cont_header, margin_left, y, text_width,
                        font_name="Helvetica-Bold", font_size=10, leading=14,
                    )

                    if cont.justificativa and y > y_min:
                        y = _draw_wrapped_text(
                            c, f"  Justificativa: {cont.justificativa}",
                            margin_left, y, text_width,
                            font_name="Helvetica", font_size=10, leading=13,
                        )

                    if cont.aprovado_por_supervisor and y > y_min:
                        aprov = cont.aprovado_por_supervisor
                        y = _draw_wrapped_text(
                            c, f"  Supervisor: Aprovado por {aprov.get_full_name() or aprov.username}",
                            margin_left, y, text_width,
                            font_name="Helvetica", font_size=10, leading=13,
                        )

                    if cont.aprovado_por_ordenador and y > y_min:
                        aprov = cont.aprovado_por_ordenador
                        y = _draw_wrapped_text(
                            c, f"  Ordenador: Aprovado por {aprov.get_full_name() or aprov.username}",
                            margin_left, y, text_width,
                            font_name="Helvetica", font_size=10, leading=13,
                        )

                    if cont.aprovado_por_conselho and y > y_min:
                        aprov = cont.aprovado_por_conselho
                        y = _draw_wrapped_text(
                            c, f"  Conselho: Aprovado por {aprov.get_full_name() or aprov.username}",
                            margin_left, y, text_width,
                            font_name="Helvetica", font_size=10, leading=13,
                        )

                    y -= 8
            else:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(
                    margin_left, y,
                    "Nenhuma contingência ou retificação excepcional registrada para este processo.",
                )
                y -= 16

        y -= 10

        # --- BOILERPLATE LEGAL ---
        if y > y_min:
            c.setLineWidth(0.5)
            c.line(margin_left, y, width - margin_right, y)
            y -= 14
            boilerplate = (
                "O Conselho Fiscal manifesta-se pela REGULARIDADE das despesas, "
                "conforme histórico auditado acima."
            )
            _draw_wrapped_text(c, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

        # --- BLOCOS DE ASSINATURA (3 conselheiros) ---
        positions = [
            (margin_left + _COUNCIL_SIG_WIDTH / 2, "Conselheiro(a) Fiscal 1"),
            (width / 2.0, "Conselheiro(a) Fiscal 2"),
            (width - margin_right - _COUNCIL_SIG_WIDTH / 2, "Conselheiro(a) Fiscal 3"),
        ]
        c.setFont("Helvetica", 9)
        for sig_x, label in positions:
            c.line(sig_x - _COUNCIL_SIG_WIDTH / 2, _COUNCIL_SIG_Y, sig_x + _COUNCIL_SIG_WIDTH / 2, _COUNCIL_SIG_Y)
            c.drawCentredString(sig_x, _COUNCIL_SIG_Y - 12, label)


class TermoAuditoriaDocument(BasePDFDocument):
    """Generates the 'Termo de Auditoria' PDF for a given Processo."""

    def draw_content(self):
        processo = self.obj
        c = self.canvas
        width = self.page_width
        height = self.page_height

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right

        y = height - 160

        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2.0, y, "TERMO DE AUDITORIA")
        y -= 18
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(width / 2.0, y, f"PROCESSO Nº {processo.id}")
        y -= 28

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 20

        c.setFont("Helvetica", 11)
        c.drawString(margin_left, y, f"Credor: {processo.credor.nome if processo.credor else 'Não informado'}")
        y -= 16
        c.drawString(margin_left, y, f"Valor Líquido: {_formatar_moeda(processo.valor_liquido)}")
        y -= 16
        c.drawString(
            margin_left,
            y,
            f"Data de Auditoria: {date.today().strftime('%d/%m/%Y')}",
        )
        y -= 24

        texto = (
            "Certifico, para os devidos fins, que o processo foi auditado e que os "
            "documentos apresentados atendem aos requisitos formais e materiais "
            "para continuidade do fluxo institucional."
        )
        y = _draw_wrapped_text(c, texto, margin_left, y, text_width, font_name="Helvetica", font_size=11)
        y -= 30

        sig_x = width / 2.0
        c.setFont("Helvetica", 10)
        c.drawCentredString(sig_x, _AUTH_SIG_Y + _AUTH_SIG_DATE_OFFSET, "Local e Data: _____________________________, _____ / _____ / _________")
        c.line(sig_x - _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y, sig_x + _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y)
        c.drawCentredString(sig_x, _AUTH_SIG_Y - 14, "Responsável pela Auditoria")


class ReciboDocument(BasePDFDocument):
    """Generates a 'Recibo de Pagamento' PDF for the four verba types:
    ReembolsoCombustivel, AuxilioRepresentacao, Jeton, and SuprimentoDeFundos.

    The correct ``tipo_verba``, ``beneficiario``, and ``valor`` are derived
    automatically from ``self.obj.__class__.__name__``.
    """

    def draw_content(self):
        obj = self.obj
        c = self.canvas
        page_width = self.page_width

        # --- Dispatch: map class to (tipo_verba, beneficiario, valor) ---
        _RECIBO_DISPATCH = {
            'ReembolsoCombustivel': (
                "Reembolso de Combustível",
                lambda o: o.beneficiario,
                lambda o: o.valor_total,
            ),
            'AuxilioRepresentacao': (
                "Auxílio Representação",
                lambda o: o.beneficiario,
                lambda o: o.valor_total,
            ),
            'Jeton': (
                "Jeton",
                lambda o: o.beneficiario,
                lambda o: o.valor_total,
            ),
            'SuprimentoDeFundos': (
                "Suprimento de Fundos",
                lambda o: o.suprido,
                # SuprimentoDeFundos stores the approved amount as valor_liquido
                lambda o: o.valor_liquido,
            ),
        }

        class_name = obj.__class__.__name__
        dispatch = _RECIBO_DISPATCH.get(class_name)
        if dispatch is None:
            raise ValueError(
                f"ReciboDocument não suporta o tipo '{class_name}'. "
                f"Tipos aceitos: {', '.join(_RECIBO_DISPATCH)}."
            )
        tipo_verba, get_beneficiario, get_valor = dispatch
        beneficiario = get_beneficiario(obj)
        valor = get_valor(obj)

        valor_formatado = _formatar_moeda(valor)
        beneficiario_nome = beneficiario.nome if beneficiario else "N/A"
        beneficiario_cpf = beneficiario.cpf_cnpj if beneficiario else "N/A"

        # --- CABEÇALHO ---
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 620, "RECIBO DE PAGAMENTO")

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(page_width / 2, 590, tipo_verba.upper())

        # --- TEXTO DA DECLARAÇÃO ---
        declaration = (
            f"Recebi do Conselho Regional de Corretores de Imóveis de Santa Catarina - "
            f"11ª Região (CRECI-SC), a importância líquida de {valor_formatado}, "
            f"referente ao pagamento de {tipo_verba}."
        )
        margin_left = 72
        text_width = page_width - 2 * margin_left
        _draw_wrapped_text(
            c, declaration, margin_left, 540, text_width,
            font_name="Helvetica", font_size=12,
        )

        # --- DADOS DO BENEFICIÁRIO ---
        c.setFont("Helvetica", 11)
        c.drawString(margin_left, 450, f"Beneficiário / Recebedor: {beneficiario_nome}")
        c.drawString(margin_left, 434, f"CPF / CNPJ: {beneficiario_cpf}")

        # --- BLOCO DE ASSINATURA ---
        sig_x = page_width / 2
        c.line(sig_x - 130, 250, sig_x + 130, 250)
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 265, beneficiario_nome)
        c.drawCentredString(sig_x, 236, "Assinatura do Recebedor")
        c.drawCentredString(sig_x, 220, "Local e Data: Florianópolis, _____ / _____ / _________")


DOCUMENT_REGISTRY = {
    'scd': SCDDocument,
    'contabilizacao': TermoContabilizacaoDocument,
    'auditoria': TermoAuditoriaDocument,
    'ateste': TermoAtesteDocument,
    'autorizacao': AutorizacaoDocument,
    'pcd': PCDDocument,
    'conselho_fiscal': ConselhoFiscalDocument,
    'recibo_reembolso': ReciboDocument,
    'recibo_auxilio': ReciboDocument,
    'recibo_jeton': ReciboDocument,
    'recibo_suprimento': ReciboDocument,
}


def gerar_documento_pdf(doc_type, obj, **kwargs):
    """
    Factory function that instantiates the appropriate document class and
    generates the PDF, returning the final merged PDF as bytes.
    """
    doc_class = DOCUMENT_REGISTRY.get(doc_type.lower())
    if not doc_class:
        raise ValueError(f"Tipo de documento '{doc_type}' não reconhecido.")
    documento = doc_class(obj, **kwargs)
    return documento.generate()
