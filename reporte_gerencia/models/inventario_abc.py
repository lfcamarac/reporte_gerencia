# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools

class ReporteGerenciaInventarioABC(models.Model):
    _name = 'reporte.gerencia.inventario.abc'
    _description = 'Clasificación ABC de Inventario'
    _auto = False
    _order = 'total_value desc'

    product_id = fields.Many2one('product.product', 'Producto', readonly=True)
    categ_id = fields.Many2one('product.category', 'Categoría', readonly=True)
    stock = fields.Float('Existencia', readonly=True)
    cost = fields.Float('Costo Unitario', readonly=True)
    total_value = fields.Float('Valor del Inventario', readonly=True)
    cumulative_percentage = fields.Float('% Acumulado', readonly=True)
    classification = fields.Selection([
        ('A', 'Alta Rotación/Valor (A)'),
        ('B', 'Media Rotación/Valor (B)'),
        ('C', 'Baja Rotación/Valor (C)')
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
                        pp.standard_price as cost,
                        SUM(COALESCE(sq.quantity, 0)) * pp.standard_price as total_value
                    FROM product_product pp
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    LEFT JOIN stock_quant sq ON sq.product_id = pp.id
                    WHERE pt.type = 'product'
                    GROUP BY pp.id, pt.categ_id, pp.standard_price
                    HAVING SUM(COALESCE(sq.quantity, 0)) > 0
                ),
                total_inv AS (
                    SELECT SUM(total_value) as grand_total FROM product_values
                ),
                calculated_abc AS (
                    SELECT 
                        pv.*,
                        ti.grand_total,
                        SUM(pv.total_value) OVER (ORDER BY pv.total_value DESC) as cumulative_value,
                        (SUM(pv.total_value) OVER (ORDER BY pv.total_value DESC) / NULLIF(ti.grand_total, 0)) * 100 as cumulative_percentage
                    FROM product_values pv, total_inv ti
                )
                SELECT 
                    product_id AS id,
                    product_id,
                    categ_id,
                    stock,
                    cost,
                    total_value,
                    cumulative_percentage,
                    CASE 
                        WHEN cumulative_percentage <= 80 THEN 'A'
                        WHEN cumulative_percentage <= 95 THEN 'B'
                        ELSE 'C'
                    END as classification
                FROM calculated_abc
            )
        """ % self._table)
