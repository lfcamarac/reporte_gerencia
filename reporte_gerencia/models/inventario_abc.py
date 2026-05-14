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
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH product_values AS (
                    SELECT 
                        pp.id AS product_id,
                        pt.categ_id,
                        SUM(COALESCE(sq.quantity, 0)) as stock,
                        -- Costo en BS
                        pt.standard_price as cost,
                        -- Costo en USD
                        pt.standard_price_usd as cost_usd,
                        -- Valores Totales
                        SUM(COALESCE(sq.quantity, 0)) * pt.standard_price as total_value,
                        SUM(COALESCE(sq.quantity, 0)) * pt.standard_price_usd as total_value_usd
                    FROM product_product pp
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    LEFT JOIN stock_quant sq ON sq.product_id = pp.id
                    LEFT JOIN stock_location sl ON sl.id = sq.location_id
                    WHERE pt.type = 'product'
                    AND (sl.usage = 'internal' OR sl.id IS NULL)
                    GROUP BY pp.id, pt.categ_id, pt.standard_price, pt.standard_price_usd
                ),
                total_inv AS (
                    SELECT SUM(total_value_usd) as grand_total FROM product_values
                ),
                calculated_abc AS (
                    SELECT 
                        pv.*,
                        ti.grand_total,
                        SUM(pv.total_value_usd) OVER (ORDER BY pv.total_value_usd DESC) as cumulative_value,
                        (SUM(pv.total_value_usd) OVER (ORDER BY pv.total_value_usd DESC) / NULLIF(ti.grand_total, 0)) * 100 as cumulative_percentage
                    FROM product_values pv, total_inv ti
                )
                SELECT 
                    row_number() OVER () AS id,
                    product_id,
                    categ_id,
                    stock,
                    cost,
                    total_value,
                    cost_usd,
                    total_value_usd,
                    COALESCE(cumulative_percentage, 0) as cumulative_percentage,
                    CASE 
                        WHEN cumulative_percentage <= 80 THEN 'A'
                        WHEN cumulative_percentage <= 95 THEN 'B'
                        ELSE 'C'
                    END as classification
                FROM calculated_abc
            )
        """ % self._table)
