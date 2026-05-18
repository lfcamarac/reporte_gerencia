# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools

class ReporteGerenciaInventarioABC(models.Model):
    _name = 'reporte.gerencia.inventario.abc'
    _description = 'Clasificación ABC de Inventario'
    _auto = False
    _order = 'total_value_usd desc'

    product_id = fields.Many2one('product.product', 'Producto', readonly=True)
    categ_id = fields.Many2one('product.category', 'Categoría', readonly=True)
    main_categ_name = fields.Char('Categoría Principal', readonly=True)
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
                WITH product_stock AS (
                    -- Obtener stock consolidado por producto en ubicaciones internas
                    SELECT 
                        sq.product_id,
                        SUM(sq.quantity) AS quantity
                    FROM stock_quant sq
                    JOIN stock_location sl ON sl.id = sq.location_id
                    WHERE sl.usage = 'internal'
                    GROUP BY sq.product_id
                ),
                product_values AS (
                    -- Calcular valores base por producto
                    SELECT 
                        pp.id AS product_id,
                        pt.categ_id AS categ_id,
                        CAST(NULLIF(SPLIT_PART(pc.parent_path, '/', 1), '') AS INTEGER) AS main_categ_id,
                        COALESCE(ps.quantity, 0) AS stock,
                        -- Costo en BS (JSONB en Odoo 18)
                        (COALESCE(pp.standard_price->>'1', '0'))::numeric AS cost,
                        -- Costo en USD (campo custom de base_contable en template)
                        COALESCE(pt.standard_price_usd, 0) AS cost_usd,
                        -- Valores Totales
                        COALESCE(ps.quantity, 0) * (COALESCE(pp.standard_price->>'1', '0'))::numeric AS total_value,
                        COALESCE(ps.quantity, 0) * COALESCE(pt.standard_price_usd, 0) AS total_value_usd
                    FROM product_product pp
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    JOIN product_category pc ON pc.id = pt.categ_id
                    LEFT JOIN product_stock ps ON ps.product_id = pp.id
                    WHERE (pt.is_storable = True OR pt.type = 'product')
                    AND pt.active = True
                ),
                total_inv AS (
                    SELECT SUM(total_value_usd) AS grand_total FROM product_values
                ),
                calculated_abc AS (
                    -- Calcular porcentajes y acumulados para el ranking ABC
                    SELECT 
                        pv.*,
                        COALESCE(rc.name, 'Sin Categoría') AS main_categ_name,
                        ti.grand_total,
                        SUM(pv.total_value_usd) OVER (ORDER BY pv.total_value_usd DESC, pv.product_id ASC) AS cumulative_value
                    FROM product_values pv
                    CROSS JOIN total_inv ti
                    LEFT JOIN product_category rc ON rc.id = pv.main_categ_id
                )
                SELECT 
                    row_number() OVER (ORDER BY total_value_usd DESC, product_id ASC) AS id,
                    product_id,
                    categ_id,
                    main_categ_name,
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
