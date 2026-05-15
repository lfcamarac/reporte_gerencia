# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools

class ReporteGerenciaCompras(models.Model):
    _name = 'reporte.gerencia.compras'
    _description = 'Vista Consolidada de Compras Gerenciales'
    _auto = False
    _order = 'date desc'

    date = fields.Date('Fecha', readonly=True)
    product_id = fields.Many2one('product.product', 'Producto', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Proveedor', readonly=True)
    categ_id = fields.Many2one('product.category', 'Categoría', readonly=True)
    main_categ_id = fields.Many2one('product.category', 'ID Categoría Principal', readonly=True)
    main_categ_name = fields.Char('Categoría Principal', readonly=True)
    quantity = fields.Float('Unidades', readonly=True)
    price_total = fields.Float('Monto Total (Bs)', readonly=True)
    price_total_usd = fields.Float('Monto Total ($)', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH consolidated_purchases AS (
                    SELECT
                        po.date_order AS date,
                        pol.product_id AS product_id,
                        po.partner_id AS partner_id,
                        pt.categ_id AS categ_id,
                        CAST(NULLIF(SPLIT_PART(pc.parent_path, '/', 1), '') AS INTEGER) AS main_categ_id,
                        pol.product_qty AS quantity,
                        pol.price_total AS price_total,
                        (pol.price_total / NULLIF(po.x_tasa, 0)) AS price_total_usd
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON po.id = pol.order_id
                    JOIN product_product pp ON pp.id = pol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    JOIN product_category pc ON pc.id = pt.categ_id
                    WHERE po.state IN ('purchase', 'done')
                )
                SELECT
                    row_number() OVER () AS id,
                    p.date,
                    p.product_id,
                    p.partner_id,
                    p.categ_id,
                    p.main_categ_id,
                    rc.name AS main_categ_name,
                    p.quantity,
                    p.price_total,
                    p.price_total_usd
                FROM consolidated_purchases p
                LEFT JOIN product_category rc ON rc.id = p.main_categ_id
            )
        """ % self._table)
