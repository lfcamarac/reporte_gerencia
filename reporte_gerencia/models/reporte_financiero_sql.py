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

    @api.model
    def _refresh_materialized_view(self):
        self.env.cr.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY %s" % self._table
        )

    def init(self):
        cr = self.env.cr
        cr.execute("DROP MATERIALIZED VIEW IF EXISTS %s CASCADE" % self._table)
        tools.drop_view_if_exists(cr, self._table)
        cr.execute("""
            CREATE MATERIALIZED VIEW {table} AS (
                WITH usd_rate_fallback AS (
                    SELECT 1.0 / NULLIF(rate, 0) AS tasa
                    FROM res_currency_rate
                    WHERE currency_id = (SELECT id FROM res_currency WHERE name = 'USD' LIMIT 1)
                    ORDER BY name DESC
                    LIMIT 1
                )
                SELECT
                    aml.id AS id,
                    aml.date AS date,
                    aml.partner_id AS partner_id,
                    acc.account_type AS account_type,
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
                    CASE
                        WHEN acc.account_type = 'asset_receivable' THEN (aml.debit / NULLIF(
                            COALESCE(NULLIF(am.tasa, 0), (SELECT tasa FROM usd_rate_fallback)), 0))
                        WHEN acc.account_type = 'liability_payable' THEN (aml.credit / NULLIF(
                            COALESCE(NULLIF(am.tasa, 0), (SELECT tasa FROM usd_rate_fallback)), 0))
                        ELSE 0
                    END AS invoiced_amount_usd,
                    CASE
                        WHEN acc.account_type = 'asset_receivable' THEN (aml.credit / NULLIF(
                            COALESCE(NULLIF(am.tasa, 0), (SELECT tasa FROM usd_rate_fallback)), 0))
                        WHEN acc.account_type = 'liability_payable' THEN (aml.debit / NULLIF(
                            COALESCE(NULLIF(am.tasa, 0), (SELECT tasa FROM usd_rate_fallback)), 0))
                        ELSE 0
                    END AS paid_amount_usd,
                    ((aml.debit - aml.credit) / NULLIF(
                        COALESCE(NULLIF(am.tasa, 0), (SELECT tasa FROM usd_rate_fallback)), 0))
                        * (CASE WHEN acc.account_type = 'liability_payable' THEN -1 ELSE 1 END) AS balance_usd
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account acc ON acc.id = aml.account_id
                WHERE acc.account_type IN ('asset_receivable', 'liability_payable')
                  AND aml.parent_state = 'posted'
            ) WITH DATA
        """.format(table=self._table))
        cr.execute(
            "CREATE UNIQUE INDEX {table}_id_uniq ON {table}(id)".format(table=self._table)
        )
        cr.execute(
            "CREATE INDEX {table}_date_idx ON {table}(date)".format(table=self._table)
        )
        cr.execute(
            "CREATE INDEX {table}_acct_partner_idx ON {table}(account_type, partner_id)".format(table=self._table)
        )
