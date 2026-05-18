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
    main_categ_id = fields.Many2one('product.category', 'ID Categoría Principal', readonly=True)
    main_categ_name = fields.Char('Categoría Principal', readonly=True)
    quantity = fields.Float('Cantidad', readonly=True)
    price_total = fields.Float('Venta Total (Bs)', readonly=True)
    price_total_usd = fields.Float('Venta Total ($)', readonly=True)
    cost_total = fields.Float('Costo Total (Bs)', readonly=True)
    cost_total_usd = fields.Float('Costo Total ($)', readonly=True)
    margin = fields.Float('Utilidad (Bs)', readonly=True)
    margin_usd = fields.Float('Utilidad ($)', readonly=True)
    source = fields.Selection([('pos', 'Punto de Venta'), ('sale', 'Ventas Oficina'), ('invoice', 'Factura Directa')], 'Origen', readonly=True)
    order_id = fields.Integer('ID Pedido', readonly=True)
    order_ref = fields.Char('Referencia de Pedido', readonly=True)
    order_count = fields.Float('Contador de Pedidos', readonly=True)

    def init(self):
        # Force refresh of the SQL view with correct table aliases
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH consolidated_sales AS (
                    -- VENTAS DE POS
                    SELECT
                        pol.create_date AS date,
                        pol.product_id AS product_id,
                        pt.categ_id AS categ_id,
                        CAST(NULLIF(SPLIT_PART(pc.parent_path, '/', 1), '') AS INTEGER) AS main_categ_id,
                        pol.qty AS quantity,
                        pol.price_subtotal_incl AS price_total,
                        pol.price_subtotal_incl_ref AS price_total_usd,
                        COALESCE(pol.total_cost, 0) AS cost_total,
                        (COALESCE(pol.total_cost, 0) / NULLIF(po.currency_rate_ref, 0)) AS cost_total_usd,
                        'pos' AS source,
                        po.id AS order_id,
                        'POS/' || po.id::text AS order_ref
                    FROM pos_order_line pol
                    JOIN pos_order po ON po.id = pol.order_id
                    JOIN product_product pp ON pp.id = pol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    JOIN product_category pc ON pc.id = pt.categ_id
                    WHERE po.state IN ('paid', 'done', 'invoiced')

                    UNION ALL

                    -- VENTAS DE OFICINA (SALE ORDERS)
                    SELECT
                        sol.create_date AS date,
                        sol.product_id AS product_id,
                        pt.categ_id AS categ_id,
                        CAST(NULLIF(SPLIT_PART(pc.parent_path, '/', 1), '') AS INTEGER) AS main_categ_id,
                        sol.product_uom_qty AS quantity,
                        sol.price_total AS price_total,
                        (sol.price_total / NULLIF(so.x_tasa, 0)) AS price_total_usd,
                        (sol.product_uom_qty * COALESCE(sol.purchase_price, 0)) AS cost_total,
                        ((sol.product_uom_qty * COALESCE(sol.purchase_price, 0)) / NULLIF(so.x_tasa, 0)) AS cost_total_usd,
                        'sale' AS source,
                        so.id AS order_id,
                        'SO/' || so.id::text AS order_ref
                    FROM sale_order_line sol
                    JOIN sale_order so ON so.id = sol.order_id
                    JOIN product_product pp ON pp.id = sol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    JOIN product_category pc ON pc.id = pt.categ_id
                    WHERE so.state IN ('sale', 'done') AND sol.product_uom_qty > 0

                    UNION ALL

                    -- FACTURAS DIRECTAS (AJUSTES O VENTAS SIN PEDIDO)
                    SELECT
                        am.invoice_date::timestamp AS date,
                        aml.product_id AS product_id,
                        pt.categ_id AS categ_id,
                        CAST(NULLIF(SPLIT_PART(pc.parent_path, '/', 1), '') AS INTEGER) AS main_categ_id,
                        aml.quantity AS quantity,
                        aml.price_total AS price_total,
                        (aml.price_total / NULLIF(am.tasa, 0)) AS price_total_usd,
                        -- Intento de obtener costo de la valoración de stock si está disponible
                        COALESCE((
                            SELECT SUM(svl.remaining_value) 
                            FROM stock_valuation_layer svl 
                            WHERE svl.product_id = aml.product_id 
                            AND svl.stock_move_id IN (
                                SELECT stock_move_id FROM stock_move_line WHERE picking_id IN (
                                    SELECT picking_id FROM stock_picking WHERE sale_id IS NULL
                                )
                            ) LIMIT 1
                        ), 0) AS cost_total,
                        (COALESCE((
                            SELECT SUM(svl.remaining_value) 
                            FROM stock_valuation_layer svl 
                            WHERE svl.product_id = aml.product_id 
                            AND svl.stock_move_id IN (
                                SELECT stock_move_id FROM stock_move_line WHERE picking_id IN (
                                    SELECT picking_id FROM stock_picking WHERE sale_id IS NULL
                                )
                            ) LIMIT 1
                        ), 0) / NULLIF(am.tasa, 0)) AS cost_total_usd,
                        'invoice' AS source,
                        am.id AS order_id,
                        'INV/' || am.id::text AS order_ref
                    FROM account_move_line aml
                    JOIN account_move am ON am.id = aml.move_id
                    JOIN product_product pp ON pp.id = aml.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    JOIN product_category pc ON pc.id = pt.categ_id
                    WHERE am.move_type IN ('out_invoice', 'out_refund')
                    AND am.state = 'posted'
                    AND aml.display_type = 'product'
                    -- Excluir las que ya vienen de SO o POS para evitar duplicidad
                    AND am.id NOT IN (SELECT DISTINCT invoice_id FROM pos_order WHERE invoice_id IS NOT NULL)
                    AND aml.sale_line_ids IS NULL
                ),
                numbered_sales AS (
                    SELECT 
                        s.*,
                        CAST(NULLIF(SPLIT_PART(pc.parent_path, '/', 1), '') AS INTEGER) AS main_categ_id,
                        pol.qty AS quantity,
                        ...
                        SELECT
                        row_number() OVER () AS id,
                        s.date,
                        s.product_id,
                        s.categ_id,
                        s.main_categ_id,
                        COALESCE(rc.name, 'Sin Categoría') AS main_categ_name,
                        s.quantity,
                        s.price_total,
                        s.price_total_usd,
                        s.cost_total,
                        s.cost_total_usd,
                        (s.price_total - s.cost_total) AS margin,
                        (s.price_total_usd - s.cost_total_usd) AS margin_usd,
                        s.source,
                        s.order_id,
                        s.order_ref,
                        CASE WHEN s.row_idx = 1 THEN 1.0 ELSE 0.0 END AS order_count
                        FROM numbered_sales s
                        LEFT JOIN product_category rc ON rc.id = s.main_categ_id
                        )
                        """ % self._table)
