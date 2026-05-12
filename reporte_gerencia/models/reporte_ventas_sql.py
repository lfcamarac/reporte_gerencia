# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools

class ReporteGerenciaVentas(models.Model):
    _name = 'reporte.gerencia.ventas'
    _description = 'Vista Consolidada de Ventas Gerenciales'
    _auto = False
    _order = 'date desc'

    date = fields.Datetime('Fecha', readonly=True)
    product_id = fields.Many2one('product.product', 'Producto', readonly=True)
    categ_id = fields.Many2one('product.category', 'Categoría', readonly=True)
    main_categ_id = fields.Many2one('product.category', 'Categoría Principal', readonly=True)
    quantity = fields.Float('Cantidad', readonly=True)
    price_total = fields.Float('Venta Total (Bs)', readonly=True)
    price_total_usd = fields.Float('Venta Total ($)', readonly=True)
    cost_total = fields.Float('Costo Total (Bs)', readonly=True)
    cost_total_usd = fields.Float('Costo Total ($)', readonly=True)
    margin = fields.Float('Utilidad (Bs)', readonly=True)
    margin_usd = fields.Float('Utilidad ($)', readonly=True)
    source = fields.Selection([('pos', 'Punto de Venta'), ('sale', 'Ventas Oficina')], 'Origen', readonly=True)
    order_id = fields.Integer('ID Pedido', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                -- VENTAS DE POS
                SELECT
                    row_number() OVER () AS id,
                    pol.create_date AS date,
                    pol.product_id AS product_id,
                    pt.categ_id AS categ_id,
                    CAST(SPLIT_PART(pc.parent_path, '/', 1) AS INTEGER) AS main_categ_id,
                    pol.qty AS quantity,
                    pol.price_subtotal_incl AS price_total,
                    pol.price_subtotal_incl_ref AS price_total_usd,
                    (pol.qty * CAST(COALESCE(pp.standard_price->>po.company_id::text, pp.standard_price->>'0', '0') AS NUMERIC)) AS cost_total,
                    (pol.qty * pp.standard_price_usd) AS cost_total_usd,
                    (pol.price_subtotal_incl - (pol.qty * CAST(COALESCE(pp.standard_price->>po.company_id::text, pp.standard_price->>'0', '0') AS NUMERIC))) AS margin,
                    (pol.price_subtotal_incl_ref - (pol.qty * pp.standard_price_usd)) AS margin_usd,
                    'pos' AS source,
                    po.id AS order_id
                FROM pos_order_line pol
                JOIN pos_order po ON po.id = pol.order_id
                JOIN product_product pp ON pp.id = pol.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                JOIN product_category pc ON pc.id = pt.categ_id
                WHERE po.state IN ('paid', 'done', 'invoiced')

                UNION ALL

                -- VENTAS DE OFICINA (SALE ORDERS)
                SELECT
                    row_number() OVER () + 10000000 AS id,
                    sol.create_date AS date,
                    sol.product_id AS product_id,
                    pt.categ_id AS categ_id,
                    CAST(SPLIT_PART(pc.parent_path, '/', 1) AS INTEGER) AS main_categ_id,
                    sol.product_uom_qty AS quantity,
                    sol.price_total AS price_total,
                    (sol.price_total / NULLIF(so.x_tasa, 0)) AS price_total_usd,
                    (sol.product_uom_qty * CAST(COALESCE(pp.standard_price->>so.company_id::text, pp.standard_price->>'0', '0') AS NUMERIC)) AS cost_total,
                    (sol.product_uom_qty * pp.standard_price_usd) AS cost_total_usd,
                    (sol.price_total - (sol.product_uom_qty * CAST(COALESCE(pp.standard_price->>so.company_id::text, pp.standard_price->>'0', '0') AS NUMERIC))) AS margin,
                    ((sol.price_total / NULLIF(so.x_tasa, 0)) - (sol.product_uom_qty * pp.standard_price_usd)) AS margin_usd,
                    'sale' AS source,
                    so.id AS order_id
                FROM sale_order_line sol
                JOIN sale_order so ON so.id = sol.order_id
                JOIN product_product pp ON pp.id = sol.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                JOIN product_category pc ON pc.id = pt.categ_id
                WHERE so.state IN ('sale', 'done') AND sol.product_uom_qty > 0
            )
        """ % self._table)
