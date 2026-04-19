"""Geradores de PDF para documentos de verbas indenizatórias.

Este módulo implementa classes para geração de PDFs de propostas,
solicitações e recibos de diárias, reembolsos, jetons, auxílios e
documentos correlatos.
"""
from commons.shared.pdf_tools import BasePDFDocument, _draw_wrapped_text
from commons.shared.text_tools import format_brl_currency


_PCD_SIG_Y = 120
_PCD_SIG_HALF_WIDTH = 130
_SCD_SIG_Y = 200
_SCD_SIG_LABEL_Y = 186


def _safe_text(value, fallback="Não informado"):
	"""Retorna texto normalizado para exibição."""
	if value is None:
		return fallback
	text = str(value).strip()
	return text or fallback


def _format_date(value, fallback="Não informado"):
	"""Formata datas no padrão brasileiro."""
	return value.strftime('%d/%m/%Y') if value else fallback


def _get_cargo_funcao(beneficiario):
	"""Obtém cargo/função do beneficiário."""
	return _safe_text(getattr(beneficiario, "cargo_funcao", None))


def _get_data_evento(obj):
	"""Resolve data de evento por campo próprio ou por contexto do processo."""
	data_evento = getattr(obj, "data_evento", None)
	if data_evento:
		return _format_date(data_evento)
	processo = getattr(obj, "processo", None)
	reuniao_conselho = getattr(processo, "reuniao_conselho", None) if processo else None
	return _format_date(getattr(reuniao_conselho, "data_reuniao", None))


class PCDDocument(BasePDFDocument):
	"""Gera o PDF da Proposta de Concessão de Diárias (PCD)."""

	def draw_content(self):
		"""Desenha corpo da PCD no canvas."""
		diaria = self.obj
		c = self.canvas
		width = self.page_width
		height = self.page_height

		margin_left = 70
		margin_right = 70
		text_width = width - margin_left - margin_right

		y = height - 160

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

		nome = str(diaria.beneficiario.nome) if diaria.beneficiario and diaria.beneficiario.nome else "Não informado"
		cargo = _get_cargo_funcao(diaria.beneficiario)

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "DADOS DO BENEFICIÁRIO:")
		y -= 16
		c.setFont("Helvetica", 11)
		c.drawString(margin_left, y, f"Nome:              {nome}")
		y -= 16
		c.drawString(margin_left, y, f"Cargo / Função: {cargo}")
		y -= 24

		if diaria.proponente:
			c.setFont("Helvetica-Bold", 11)
			c.drawString(margin_left, y, "PROPONENTE:")
			y -= 16
			c.setFont("Helvetica", 11)
			nome_p = diaria.proponente.get_full_name() or diaria.proponente.username
			cargo_p = "Não informado"
			c.drawString(margin_left, y, f"Nome:              {nome_p}")
			y -= 16
			c.drawString(margin_left, y, f"Cargo / Função:    {cargo_p}")
			y -= 24

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "DADOS DA VIAGEM:")
		y -= 16
		c.setFont("Helvetica", 11)

		data_saida = diaria.data_saida.strftime('%d/%m/%Y') if diaria.data_saida else "Não informado"
		data_retorno = diaria.data_retorno.strftime('%d/%m/%Y') if diaria.data_retorno else "Não informado"

		c.drawString(margin_left, y, f"Data de Saída: {data_saida} | Data de Retorno: {data_retorno}")
		y -= 16
		y = _draw_wrapped_text(
			c,
			f"Origem / Destino: {diaria.cidade_origem or 'Não informado'} -> {diaria.cidade_destino or 'Não informado'}",
			margin_left,
			y,
			text_width,
			font_name="Helvetica",
			font_size=11,
			leading=16,
			justify=True,
		)
		if diaria.meio_de_transporte:
			c.drawString(margin_left, y, f"Meio de Transporte:      {diaria.meio_de_transporte}")
			y -= 16
		y -= 8

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "OBJETIVO DA VIAGEM:")
		y -= 16
		y = _draw_wrapped_text(
			c,
			diaria.objetivo or "Não informado.",
			margin_left,
			y,
			text_width,
			font_name="Helvetica",
			font_size=11,
			justify=True,
		)
		y -= 20

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "VALORES:")
		y -= 16
		c.setFont("Helvetica", 11)
		valor_unitario = None
		if diaria.quantidade_diarias and diaria.valor_total:
			try:
				valor_unitario = diaria.valor_total / diaria.quantidade_diarias
			except Exception:
				valor_unitario = None

		qtd = diaria.quantidade_diarias or 0
		valor_unitario_texto = format_brl_currency(valor_unitario) if valor_unitario is not None else "Não informado"
		c.drawString(margin_left, y, f"Qtd. Diárias: {qtd} | Valor Unitário: {valor_unitario_texto} | Valor Total: {format_brl_currency(diaria.valor_total)}")
		y -= 16
		y -= 12

		c.setLineWidth(0.5)
		c.line(margin_left, y, width - margin_right, y)
		y -= 14
		boilerplate = (
			"Proposta de concessão de diárias elaborada nos termos da legislação e regulamento interno vigentes, "
			"para fins de autorização pelo Ordenador de Despesas."
		)
		_draw_wrapped_text(
			c,
			boilerplate,
			margin_left,
			y,
			text_width,
			font_name="Helvetica-Oblique",
			font_size=10,
			justify=True,
		)

		sig_left_x = margin_left + _PCD_SIG_HALF_WIDTH
		sig_right_x = width - margin_right - _PCD_SIG_HALF_WIDTH

		c.setFont("Helvetica", 9)

		c.drawCentredString(sig_left_x, _PCD_SIG_Y + 26, nome)
		c.drawCentredString(sig_left_x, _PCD_SIG_Y + 14, cargo)
		c.line(sig_left_x - _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y,
			   sig_left_x + _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y)
		c.drawCentredString(sig_left_x, _PCD_SIG_Y - 12, "Assinatura do(a) Beneficiário(a)")

		c.line(sig_right_x - _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y,
			   sig_right_x + _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y)
		c.drawCentredString(sig_right_x, _PCD_SIG_Y - 12, "Ordenador(a) de Despesa")


class SCDDocument(BasePDFDocument):
	"""Gera o PDF da Solicitação de Concessão de Diárias (SCD)."""

	def draw_content(self):
		"""Desenha corpo da SCD no canvas."""
		diaria = self.obj
		c = self.canvas
		width = self.page_width

		margin_left = 70
		margin_right = 70
		text_width = width - margin_left - margin_right

		c.setFont("Helvetica-Bold", 14)
		c.drawCentredString(width / 2.0, 620, "SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS - SCD")

		c.setFont("Helvetica", 11)
		y = 550

		siscac = diaria.numero_siscac or 'N/A'
		nome_benef = diaria.beneficiario.nome if diaria.beneficiario else 'N/A'
		cargo_beneficiario = diaria.beneficiario.cargo_funcao if diaria.beneficiario and diaria.beneficiario.cargo_funcao else 'N/A'
		data_solicitacao = diaria.data_solicitacao.strftime('%d/%m/%Y') if diaria.data_solicitacao else 'N/A'
		data_saida = diaria.data_saida.strftime('%d/%m/%Y') if diaria.data_saida else 'N/A'
		data_retorno = diaria.data_retorno.strftime('%d/%m/%Y') if diaria.data_retorno else 'N/A'
		transporte = diaria.meio_de_transporte.meio_de_transporte if diaria.meio_de_transporte else 'N/A'
		nome_proponente = diaria.proponente.get_full_name() if diaria.proponente else 'N/A'
		cargo_proponente = 'Cargo não informado'
		if diaria.proponente and diaria.proponente.groups.exists():
			cargo_proponente = diaria.proponente.groups.first().name

		fields = [
			f"Data da Solicitação: {data_solicitacao}",
			f"Nº SISCAC: {siscac}",
			f"Beneficiário: {nome_benef}",
			f"Cargo do Beneficiário: {cargo_beneficiario}",
			f"Período: {data_saida} a {data_retorno}",
			f"Trajeto: {diaria.cidade_origem} para {diaria.cidade_destino}",
			f"Transporte: {transporte}",
		]
		for field in fields:
			c.drawString(margin_left, y, field)
			y -= 20

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, 430, "Objetivo:")
		_draw_wrapped_text(
			c,
			diaria.objetivo or 'N/A',
			margin_left,
			410,
			text_width,
			font_name="Helvetica",
			font_size=11,
			justify=True,
		)

		sig_left_x = margin_left + _PCD_SIG_HALF_WIDTH
		sig_right_x = width - margin_right - _PCD_SIG_HALF_WIDTH

		c.setFont("Helvetica", 10)
		c.drawCentredString(sig_right_x, _SCD_SIG_Y + 28, nome_proponente)
		c.drawCentredString(sig_right_x, _SCD_SIG_Y + 14, cargo_proponente)
		c.line(sig_right_x - _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y,
			   sig_right_x + _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y)
		c.drawCentredString(sig_right_x, _SCD_SIG_Y - 14, "Proponente")


class ReciboDocument(BasePDFDocument):
	"""Gera PDF de recibo para reembolso, auxílio e jeton."""

	def _draw_reembolso_combustivel(self, obj, beneficiario, valor_formatado):
		"""Renderiza requerimento de reembolso de combustível."""
		c = self.canvas
		page_width = self.page_width
		margin_left = 72
		text_width = page_width - 2 * margin_left

		nome = _safe_text(getattr(beneficiario, "nome", None), "N/A")
		cargo = _get_cargo_funcao(beneficiario)
		cidade_origem = _safe_text(getattr(obj, "cidade_origem", None))
		cidade_destino = _safe_text(getattr(obj, "cidade_destino", None))
		periodo = f"{_format_date(getattr(obj, 'data_saida', None))} a {_format_date(getattr(obj, 'data_retorno', None))}"
		objetivo = _safe_text(getattr(obj, "objetivo", None), "atividade não informada")

		c.setFont("Helvetica-Bold", 14)
		c.drawCentredString(page_width / 2, 620, "REQUERIMENTO DE REEMBOLSO DE COMBUSTÍVEL")

		declaration = (
			f"Eu, {nome}, {cargo}, venho por meio deste requerer o reembolso de combustível "
			f"utilizado no deslocamento entre {cidade_origem} e {cidade_destino}, no período de {periodo}, "
			f"referente a {objetivo}."
		)
		y = _draw_wrapped_text(
			c,
			declaration,
			margin_left,
			560,
			text_width,
			font_name="Helvetica",
			font_size=12,
			justify=True,
		)

		y -= 24
		c.setFont("Helvetica", 11)
		c.drawString(margin_left, y, f"Requerente: {nome}")
		y -= 16
		c.drawString(margin_left, y, f"Cargo / Função: {cargo}")
		y -= 16
		c.drawString(margin_left, y, f"Período do Deslocamento: {periodo}")
		y -= 16
		y = _draw_wrapped_text(
			c,
			f"Trajeto: {cidade_origem} -> {cidade_destino}",
			margin_left,
			y,
			text_width,
			font_name="Helvetica",
			font_size=11,
			justify=True,
		)
		y -= 4
		y = _draw_wrapped_text(
			c,
			f"Objetivo: {objetivo}",
			margin_left,
			y,
			text_width,
			font_name="Helvetica",
			font_size=11,
			justify=True,
		)
		y -= 16
		c.drawString(margin_left, y, f"Valor Requerido: {valor_formatado}")

		sig_x = page_width / 2
		c.setFont("Helvetica", 11)
		c.drawCentredString(sig_x, 258, nome)
		c.drawCentredString(sig_x, 244, cargo)
		c.line(sig_x - 130, 232, sig_x + 130, 232)
		c.drawCentredString(sig_x, 218, "Requerente")

	def _draw_recibo_evento(self, obj, beneficiario, valor_formatado, tipo_verba):
		"""Renderiza recibo de jeton ou auxílio com informações do evento."""
		c = self.canvas
		page_width = self.page_width
		margin_left = 72
		text_width = page_width - 2 * margin_left

		nome = _safe_text(getattr(beneficiario, "nome", None), "N/A")
		cargo = _get_cargo_funcao(beneficiario)
		data_evento = _get_data_evento(obj)
		local_evento = _safe_text(getattr(obj, "local_evento", None))

		if obj.__class__.__name__ == 'Jeton':
			evento = _safe_text(getattr(obj, "reuniao", None))
			declaration = (
				f"Recebi do Conselho Regional de Corretores de Imóveis de Santa Catarina - 11ª Região (CRECI-SC), "
				f"a importância líquida de {valor_formatado}, referente ao pagamento de Jeton pela participação em "
				f"{evento}, realizada em {data_evento}, no local {local_evento}, na qualidade de {cargo}."
			)
		else:
			evento = _safe_text(getattr(obj, "objetivo", None), "atividade de representação não informada")
			declaration = (
				f"Recebi do Conselho Regional de Corretores de Imóveis de Santa Catarina - 11ª Região (CRECI-SC), "
				f"a importância líquida de {valor_formatado}, referente ao pagamento de Auxílio Representação para "
				f"{evento}, realizado em {data_evento}, no local {local_evento}, na qualidade de {cargo}."
			)

		c.setFont("Helvetica-Bold", 14)
		c.drawCentredString(page_width / 2, 620, "RECIBO DE PAGAMENTO")

		c.setFont("Helvetica-Bold", 12)
		c.drawCentredString(page_width / 2, 590, tipo_verba.upper())

		y = _draw_wrapped_text(
			c,
			declaration,
			margin_left,
			540,
			text_width,
			font_name="Helvetica",
			font_size=12,
			justify=True,
		)

		y -= 20
		c.setFont("Helvetica", 11)
		c.drawString(margin_left, y, f"Beneficiário / Recebedor: {nome}")
		y -= 16
		c.drawString(margin_left, y, f"Cargo / Função: {cargo}")
		y -= 16
		y = _draw_wrapped_text(
			c,
			f"Evento: {evento}",
			margin_left,
			y,
			text_width,
			font_name="Helvetica",
			font_size=11,
			justify=True,
		)
		y -= 4
		c.drawString(margin_left, y, f"Data do Evento: {data_evento}")
		y -= 16
		y = _draw_wrapped_text(
			c,
			f"Local do Evento: {local_evento}",
			margin_left,
			y,
			text_width,
			font_name="Helvetica",
			font_size=11,
			justify=True,
		)

		sig_x = page_width / 2
		c.setFont("Helvetica", 11)
		c.drawCentredString(sig_x, 258, nome)
		c.drawCentredString(sig_x, 244, cargo)
		c.line(sig_x - 130, 232, sig_x + 130, 232)
		c.drawCentredString(sig_x, 218, "Beneficiário(a) / Recebedor(a)")

	def draw_content(self):
		"""Desenha corpo do recibo com dispatch por tipo de objeto."""
		obj = self.obj

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

		valor_formatado = format_brl_currency(valor)

		if class_name == 'ReembolsoCombustivel':
			self._draw_reembolso_combustivel(obj, beneficiario, valor_formatado)
			return

		self._draw_recibo_evento(obj, beneficiario, valor_formatado, tipo_verba)


class TermoPrestacaoContasDocument(BasePDFDocument):
	"""Gera termo de veracidade para prestação de contas de diária."""

	def draw_content(self):
		diaria = self.obj
		c = self.canvas
		width = self.page_width
		height = self.page_height

		margin_left = 70
		margin_right = 70
		text_width = width - margin_left - margin_right
		y = height - 160

		c.setFont("Helvetica-Bold", 13)
		c.drawCentredString(width / 2.0, y, "TERMO DE PRESTAÇÃO DE CONTAS — DIÁRIA")
		y -= 24

		numero = diaria.numero_siscac or diaria.id
		beneficiario = _safe_text(getattr(diaria.beneficiario, "nome", None), "Não informado")
		c.setFont("Helvetica", 10)
		c.drawString(margin_left, y, f"Diária: {numero}")
		y -= 14
		c.drawString(margin_left, y, f"Beneficiário: {beneficiario}")
		y -= 24

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "Documentos anexados:")
		y -= 16
		c.setFont("Helvetica", 10)

		documentos = diaria.documentos.select_related("tipo").all().order_by("id")
		if not documentos:
			c.drawString(margin_left, y, "- Nenhum documento anexado.")
			y -= 14
		else:
			for indice, documento in enumerate(documentos, start=1):
				nome_arquivo = _safe_text(getattr(getattr(documento, "arquivo", None), "name", None), "Sem arquivo")
				tipo = _safe_text(getattr(documento.tipo, "tipo", None), "Sem tipo")
				y = _draw_wrapped_text(
					c,
					f"{indice}. {nome_arquivo} ({tipo})",
					margin_left,
					y,
					text_width,
					font_name="Helvetica",
					font_size=10,
					leading=14,
					justify=False,
				)

		y -= 20
		boilerplate = (
			"Declaro, para os devidos fins, que os comprovantes anexados a esta prestação de contas "
			"são autênticos, íntegros e correspondem às despesas efetivamente realizadas no contexto "
			"da diária informada."
		)
		y = _draw_wrapped_text(
			c,
			boilerplate,
			margin_left,
			y,
			text_width,
			font_name="Helvetica",
			font_size=10,
			leading=14,
			justify=True,
		)

		sig_y = max(120, y - 80)
		sig_left_x = margin_left + _PCD_SIG_HALF_WIDTH
		sig_right_x = width - margin_right - _PCD_SIG_HALF_WIDTH

		c.setFont("Helvetica", 9)
		c.line(sig_left_x - _PCD_SIG_HALF_WIDTH, sig_y, sig_left_x + _PCD_SIG_HALF_WIDTH, sig_y)
		c.drawCentredString(sig_left_x, sig_y - 12, "Beneficiário")

		c.line(sig_right_x - _PCD_SIG_HALF_WIDTH, sig_y, sig_right_x + _PCD_SIG_HALF_WIDTH, sig_y)
		c.drawCentredString(sig_right_x, sig_y - 12, "Operador / Fiscal")


# Registry de documentos específicos de Verbas Indenizatórias
VERBAS_DOCUMENT_REGISTRY = {
	'scd': SCDDocument,
	'pcd': PCDDocument,
	'termo_prestacao_contas': TermoPrestacaoContasDocument,
	'recibo_reembolso': ReciboDocument,
	'recibo_auxilio': ReciboDocument,
	'recibo_jeton': ReciboDocument,
}


__all__ = [
	"PCDDocument",
	"SCDDocument",
	"ReciboDocument",
	"TermoPrestacaoContasDocument",
	"VERBAS_DOCUMENT_REGISTRY",
]
