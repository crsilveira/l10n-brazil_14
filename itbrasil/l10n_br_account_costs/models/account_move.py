# Copyright (C) 2009  Renato Lima - Akretion
# Copyright (C) 2012  Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from functools import partial

from odoo import api, fields, models
from odoo.tools import float_is_zero
from odoo.tools.misc import formatLang
from collections import defaultdict

from ...l10n_br_fiscal.constants.fiscal import (
    CFOP_DESTINATION_EXPORT,
    FISCAL_IN
)


# class AccountMove(models.Model):
#     _inherit = "account.move"
class AccountMove(models.Model):
    _name = "account.move"
    _inherit = [
        _name,
        "l10n_br_fiscal.document.mixin.methods",
        "l10n_br_fiscal.document.invoice.mixin",
    ]
    _inherits = {"l10n_br_fiscal.document": "fiscal_document_id"}
    _order = "date DESC, name DESC"

    # @api.depends(
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
    #     'line_ids.debit',
    #     'line_ids.credit',
    #     'line_ids.currency_id',
    #     'line_ids.amount_currency',
    #     'line_ids.amount_residual',
    #     'line_ids.amount_residual_currency',
    #     'line_ids.payment_id.state',
    #     'line_ids.full_reconcile_id')
    # def _compute_amount(self):
    #     total_tax = 0.0
    #     result = super()._compute_amount()
    #     # # coloquei o len abaixo pq tem hora q traz todas as faturas do sistema
    #     # if len(self) == 1:
    #     #     # total do ICMS
    #     #     for line in self.line_ids:
    #     #         if (
    #     #             line.cfop_id
    #     #             and line.cfop_id.destination == CFOP_DESTINATION_EXPORT
    #     #             and line.fiscal_operation_id.fiscal_operation_type == FISCAL_IN
    #     #         ):
    #     #             total_tax += line.icms_value
    #     #     dif = 0.0
    #     #     total = 0.0
    #     #     # Corrige a conta de ICMS Importacao
    #     #     for line in self.line_ids:
    #     #         if (line.name and 'ICMS Entrada Importa' in line.name 
    #     #             and total_tax):
    #     #             dif = total_tax - line.debit
    #     #             line.debit = total_tax
    #     #         if (
    #     #             line.account_id and dif
    #     #             and 'Fornecedor' in line.account_id.name
    #     #         ):
    #     #             line.credit = line.credit + dif
    #     #             # menos pq o amount currency e negativo
    #     #             line.amount_currency = line.amount_currency - dif
    #     #             total += line.amount_currency + total_tax
    #     #         line._update_taxes()
    #     return result

    # @api.model_create_multi
    # def create(self, values):
    #     invoice = super().create(values)
    #     import pudb;pu.db
    #     # for line in invoice.invoice_line_ids:
    #     #     line._onchange_fiscal_tax_ids()
    #     invoice._compute_amount_others()
    #     # invoice._finalize_invoices(invoice)
    #     # for line in invoice.line_ids:
    #     #     # Use additional field helper function (for account extensions)
    #     #     line._set_additional_fields(invoice)
    #     # invoice._onchange_cash_rounding()
    #     return invoice

    # def _compute_amount_others(self):
    #     fields = self._get_amount_fields()
    #     for doc in self:
    #         values = {key: 0.0 for key in fields}
    #         for line in doc.invoice_line_ids:
    #             for field in fields:
    #                 if field in line._fields.keys():
    #                     values[field] += line[field]
    #                 if field.replace("amount_", "") in line._fields.keys():
    #                     # FIXME this field creates an error in invoice form
    #                     if field == "amount_financial_discount_value":
    #                         values[
    #                             "amount_financial_discount_value"
    #                         ] += 0  # line.financial_discount_value
    #                     else:
    #                         values[field] += line[field.replace("amount_", "")]

    #         # Valores definidos pelo Total e não pela Linha
    #         import pudb;pu.db
    #         if (
    #             doc.company_id.delivery_costs == "total"
    #             or doc.force_compute_delivery_costs_by_total
    #         ):
    #             values["amount_freight_value"] = doc.amount_freight_value
    #             values["amount_insurance_value"] = doc.amount_insurance_value
    #             values["amount_other_value"] = doc.amount_other_value
    #         if self.amount_total != doc.amount_financial_total:
    #             values["amount_financial_total"] = self.amount_total

    #         doc.update(values)

    #     # import pudb;pu.db
    #     icms = 0.0
    #     icms_up = 0.0
    #     alterado = False
    #     for line in invoice.line_ids:
    #         if line.icms_value:
    #             icms_value = line.icms_value
    #             icms += line.icms_value
    #             alterado = True
    #         if 'ICMS' in line.name:
    #             if line.debit > icms_value:
    #                 icms_up = line.debit - icms_value
    #             else:
    #                 icms_up = icms_value - line.debit
    #             if line.debit != icms_value:
    #                 if line.debit:
    #                     line.with_context(check_move_validity=False).write({'debit': icms_value})
    #                 if line.credit:
    #                     line.with_context(check_move_validity=False).write({'credit': icms_value})
    #     if alterado and icms_up:
    #         if line.account_id.user_type_id.type == "receivable":
    #             line.with_context(check_move_validity=False).write({'debit': line.debit - icms_up})
    #         if line.account_id.user_type_id.type == "payable":
    #             line.with_context(check_move_validity=False).write({'credit': line.credit - icms_up})
    #         self._recompute_dynamic_lines(recompute_all_taxes=True)
    #     return invoice
