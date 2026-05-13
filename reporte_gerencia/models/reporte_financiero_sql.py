# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools

class ReporteGerenciaFinanciero(models.Model):
    _name = 'reporte.gerencia.financiero'
    _description = 'Análisis de CxC y CxP'
    _auto = False
    _order = 'date desc'

    date = fields.Date('Fecha', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Contacto', readonly=True)
    account_type = fields.Selection([
        ('asset_receivable', 'Cuenta por Cobrar'),
        ('liability_payable', 'Cuenta por Pagar')
    ], string='Tipo', readonly=True)
    invoiced_amount = fields.Float('Facturado (Bs)', readonly=True)
    paid_amount = fields.Float('Pagado (Bs)', readonly=True)
    balance = fields.Float('Saldo (Bs)', readonly=True)
    invoiced_amount_usd = fields.Float('Facturado ($)', readonly=True)
    paid_amount_usd = fields.Float('Pagado ($)', readonly=True)
    balance_usd = fields.Float('Saldo ($)', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    aml.id AS id,
                    aml.date AS date,
                    aml.partner_id AS partner_id,
                    acc.account_type AS account_type,
                    -- Montos en BS
                    CASE 
                        WHEN acc.account_type = 'asset_receivable' THEN aml.debit 
                        WHEN acc.account_type = 'liability_payable' THEN aml.credit 
                        ELSE 0 
                    END AS invoiced_amount,
                    CASE 
                        WHEN acc.account_type = 'asset_receivable' THEN aml.credit 
                        WHEN acc.account_type = 'liability_payable' THEN aml.debit 
                        ELSE 0 
                    END AS paid_amount,
                    (aml.debit - aml.credit) * (CASE WHEN acc.account_type = 'liability_payable' THEN -1 ELSE 1 END) AS balance,
                    -- Montos en USD (usando campo tasa de account_move)
                    CASE 
                        WHEN acc.account_type = 'asset_receivable' THEN (aml.debit / NULLIF(am.tasa, 0))
                        WHEN acc.account_type = 'liability_payable' THEN (aml.credit / NULLIF(am.tasa, 0))
                        ELSE 0 
                    END AS invoiced_amount_usd,
                    CASE 
                        WHEN acc.account_type = 'asset_receivable' THEN (aml.credit / NULLIF(am.tasa, 0))
                        WHEN acc.account_type = 'liability_payable' THEN (aml.debit / NULLIF(am.tasa, 0))
                        ELSE 0 
                    END AS paid_amount_usd,
                    ((aml.debit - aml.credit) / NULLIF(am.tasa, 0)) * (CASE WHEN acc.account_type = 'liability_payable' THEN -1 ELSE 1 END) AS balance_usd
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account acc ON acc.id = aml.account_id
                WHERE acc.account_type IN ('asset_receivable', 'liability_payable')
                AND aml.parent_state = 'posted'
            )
        """ % self._table)
