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

    @api.model
    def _refresh_materialized_view(self):
        self.env.cr.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY %s" % self._table
        )

    def init(self):
        cr = self.env.cr
        cr.execute("DROP MATERIALIZED VIEW IF EXISTS %s CASCADE" % self._table)
        tools.drop_view_if_exists(cr, self._table)
        company_id = self.env.company.id
        cr.execute("""
            CREATE MATERIALIZED VIEW {table} AS (
                WITH
                -- Determinar la categoría principal considerando si la raíz es genérica
                category_root AS (
                    SELECT
                        pc.id,
                        CASE
                            WHEN root_lvl1.name IN ('ALL', 'All', 'Todos', 'all')
                                 AND NULLIF(SPLIT_PART(pc.parent_path, '/', 2), '') IS NOT NULL
                            THEN CAST(SPLIT_PART(pc.parent_path, '/', 2) AS INTEGER)
                            ELSE CAST(SPLIT_PART(pc.parent_path, '/', 1) AS INTEGER)
                        END AS root_id
                    FROM product_category pc
                    LEFT JOIN product_category root_lvl1 ON root_lvl1.id = CAST(SPLIT_PART(pc.parent_path, '/', 1) AS INTEGER)
                ),
                category_root_names AS (
                    SELECT cr.id, cr.root_id, cn.name AS root_name
                    FROM category_root cr
                    JOIN product_category cn ON cn.id = cr.root_id
                ),
                -- Tasa USD de fallback (la más reciente registrada)
                usd_rate_fallback AS (
                    SELECT 
                        1.0 / NULLIF(rate, 0) AS tasa_directa, -- Bs por 1 USD
                        rate AS tasa_inversa                   -- USD por 1 Bs
                    FROM res_currency_rate
                    WHERE currency_id = (SELECT id FROM res_currency WHERE name = 'USD' LIMIT 1)
                    ORDER BY name DESC
                    LIMIT 1
                ),
                consolidated_sales AS (
                    -- VENTAS DE POS
                    SELECT
                        pol.create_date AS date,
                        pol.product_id AS product_id,
                        pt.categ_id AS categ_id,
                        pol.qty AS quantity,
                        pol.price_subtotal AS price_total,
                        pol.price_subtotal_ref AS price_total_usd,
                        COALESCE(pol.total_cost, 0) AS cost_total,
                        (COALESCE(pol.total_cost, 0) * 
                            COALESCE(NULLIF(po.currency_rate_ref, 0), (SELECT tasa_inversa FROM usd_rate_fallback))
                        ) AS cost_total_usd,
                        'pos' AS source,
                        po.id AS order_id,
                        'POS/' || po.id::text AS order_ref,
                        'pos-' || pol.id::text AS stable_key
                    FROM pos_order_line pol
                    JOIN pos_order po ON po.id = pol.order_id
                    JOIN product_product pp ON pp.id = pol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    WHERE po.state IN ('paid', 'done', 'invoiced')

                    UNION ALL

                    -- VENTAS DE OFICINA (SALE ORDERS)
                    SELECT
                        sol.create_date AS date,
                        sol.product_id AS product_id,
                        pt.categ_id AS categ_id,
                        sol.product_uom_qty AS quantity,
                        sol.price_subtotal AS price_total,
                        (sol.price_subtotal / NULLIF(
                            COALESCE(NULLIF(so.x_tasa, 0), (SELECT tasa_directa FROM usd_rate_fallback)),
                            0)) AS price_total_usd,
                        (sol.product_uom_qty * COALESCE(sol.purchase_price, 0)) AS cost_total,
                        ((sol.product_uom_qty * COALESCE(sol.purchase_price, 0)) / NULLIF(
                            COALESCE(NULLIF(so.x_tasa, 0), (SELECT tasa_directa FROM usd_rate_fallback)),
                            0)) AS cost_total_usd,
                        'sale' AS source,
                        so.id AS order_id,
                        'SO/' || so.id::text AS order_ref,
                        'so-' || sol.id::text AS stable_key
                    FROM sale_order_line sol
                    JOIN sale_order so ON so.id = sol.order_id
                    JOIN product_product pp ON pp.id = sol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    WHERE so.state IN ('sale', 'done')
                      AND sol.product_uom_qty > 0
                      AND (sol.display_type IS NULL OR sol.display_type NOT IN ('line_section', 'line_note'))

                    UNION ALL

                    -- FACTURAS DIRECTAS (AJUSTES O VENTAS SIN PEDIDO)
                    SELECT
                        am.invoice_date::timestamp AS date,
                        aml.product_id AS product_id,
                        pt.categ_id AS categ_id,
                        aml.quantity AS quantity,
                        aml.price_subtotal AS price_total,
                        (aml.price_subtotal / NULLIF(
                            COALESCE(NULLIF(am.tasa, 0), (SELECT tasa_directa FROM usd_rate_fallback)),
                            0)) AS price_total_usd,
                        (aml.quantity * COALESCE((pp.standard_price->>'{company_id}')::numeric, 0)) AS cost_total,
                        (aml.quantity * COALESCE(pt.standard_price_usd, 0)) AS cost_total_usd,
                        'invoice' AS source,
                        am.id AS order_id,
                        'INV/' || am.id::text AS order_ref,
                        'inv-' || aml.id::text AS stable_key
                    FROM account_move_line aml
                    JOIN account_move am ON am.id = aml.move_id
                    JOIN product_product pp ON pp.id = aml.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    WHERE am.move_type IN ('out_invoice', 'out_refund')
                      AND am.state = 'posted'
                      AND aml.display_type = 'product'
                      AND NOT EXISTS (SELECT 1 FROM pos_order po2 WHERE po2.account_move = am.id)
                      AND NOT EXISTS (SELECT 1 FROM sale_order_line_invoice_rel rel WHERE rel.invoice_line_id = aml.id)
                ),
                category_hierarchy AS (
                    SELECT s.*, cr.root_id AS main_categ_id, cr.root_name AS main_categ_name
                    FROM consolidated_sales s
                    LEFT JOIN category_root_names cr ON cr.id = s.categ_id
                ),
                numbered_sales AS (
                    SELECT
                        s.*,
                        row_number() OVER (PARTITION BY s.order_ref ORDER BY s.date) AS row_idx
                    FROM category_hierarchy s
                )
                SELECT
                    row_number() OVER (ORDER BY s.date DESC, s.stable_key) AS id,
                    s.date,
                    s.product_id,
                    s.categ_id,
                    s.main_categ_id,
                    COALESCE(s.main_categ_name, 'Sin Categoría') AS main_categ_name,
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
            ) WITH DATA
        """.format(table=self._table, company_id=company_id))
        cr.execute(
            "CREATE UNIQUE INDEX {table}_id_uniq ON {table}(id)".format(table=self._table)
        )
        cr.execute(
            "CREATE INDEX {table}_date_idx ON {table}(date)".format(table=self._table)
        )
