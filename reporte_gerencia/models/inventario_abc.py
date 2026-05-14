# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools

class ReporteGerenciaInventarioABC(models.Model):
    _name = 'reporte.gerencia.inventario.abc'
    _description = 'Clasificación ABC de Inventario'
    _auto = False
    _order = 'total_value_usd desc'

    product_id = fields.Many2one('product.product', 'Producto', readonly=True)
    categ_id = fields.Many2one('product.category', 'Categoría', readonly=True)
    stock = fields.Float('Existencia', readonly=True)
    cost = fields.Float('Costo (Bs)', readonly=True)
    total_value = fields.Float('Valor (Bs)', readonly=True)
    cost_usd = fields.Float('Costo ($)', readonly=True)
    total_value_usd = fields.Float('Valor ($)', readonly=True)
    cumulative_percentage = fields.Float('% Acumulado', readonly=True)
    classification = fields.Selection([
        ('A', 'Alta Inversión (A)'),
        ('B', 'Media Inversión (B)'),
        ('C', 'Baja Inversión (C)')
    ], string='Clasificación', readonly=True)

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS %s CASCADE" % self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH product_values AS (
                    SELECT 
                        pp.id AS product_id,
                        pt.categ_id AS categ_id,
                        SUM(COALESCE(sq.quantity, 0)) AS stock,
                        -- En Odoo 18 standard_price reside físicamente en product_product
                        (COALESCE(pp.standard_price->>'1', '0'))::numeric AS cost,
                        -- standard_price_usd suele estar en product_template (base_contable)
                        COALESCE(pt.standard_price_usd, 0) AS cost_usd,
                        -- Valores Totales
                        SUM(COALESCE(sq.quantity, 0)) * (COALESCE(pp.standard_price->>'1', '0'))::numeric AS total_value,
                        SUM(COALESCE(sq.quantity, 0)) * COALESCE(pt.standard_price_usd, 0) AS total_value_usd
                    FROM product_product pp
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    LEFT JOIN stock_quant sq ON sq.product_id = pp.id
                    LEFT JOIN stock_location sl ON sl.id = sq.location_id
                    WHERE pt.type = 'product'
                    AND (sl.usage = 'internal' OR sl.id IS NULL)
                    GROUP BY pp.id, pt.categ_id, pp.standard_price, pt.standard_price_usd
                ),
                total_inv AS (
                    SELECT SUM(total_value_usd) AS grand_total FROM product_values
                ),
                calculated_abc AS (
                    SELECT 
                        pv.product_id,
                        pv.categ_id,
                        pv.stock,
                        pv.cost,
                        pv.cost_usd,
                        pv.total_value,
                        pv.total_value_usd,
                        ti.grand_total,
                        SUM(pv.total_value_usd) OVER (ORDER BY pv.total_value_usd DESC, pv.product_id ASC) AS cumulative_value
                    FROM product_values pv
                    CROSS JOIN total_inv ti
                )
                SELECT 
                    row_number() OVER (ORDER BY total_value_usd DESC, product_id ASC) AS id,
                    product_id,
                    categ_id,
                    stock,
                    cost,
                    total_value,
                    cost_usd,
                    total_value_usd,
                    CASE 
                        WHEN COALESCE(grand_total, 0) > 0 THEN (cumulative_value / grand_total) * 100 
                        ELSE 0 
                    END AS cumulative_percentage,
                    CASE 
                        WHEN COALESCE(grand_total, 0) > 0 AND (cumulative_value / grand_total) * 100 <= 80 THEN 'A'
                        WHEN COALESCE(grand_total, 0) > 0 AND (cumulative_value / grand_total) * 100 <= 95 THEN 'B'
                        ELSE 'C'
                    END AS classification
                FROM calculated_abc
            )
        """ % self._table)
