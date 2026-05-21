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
                    SELECT 
                        cr.id, 
                        cr.root_id, 
                        TRIM(SPLIT_PART(cn.name, '/', 1)) AS root_name
                    FROM category_root cr
                    JOIN product_category cn ON cn.id = cr.root_id
                ),
                usd_rate_fallback AS (
                    SELECT 1.0 / NULLIF(rate, 0) AS tasa
                    FROM res_currency_rate
                    WHERE currency_id = (SELECT id FROM res_currency WHERE name = 'USD' LIMIT 1)
                    ORDER BY name DESC
                    LIMIT 1
                ),
                consolidated_purchases AS (
                    SELECT
                        po.date_order AS date,
                        pol.product_id AS product_id,
                        po.partner_id AS partner_id,
                        pt.categ_id AS categ_id,
                        pol.product_qty AS quantity,
                        pol.price_subtotal AS price_total,
                        (pol.price_subtotal / NULLIF(
                            COALESCE(NULLIF(po.x_tasa, 0), (SELECT tasa FROM usd_rate_fallback)),
                            0)) AS price_total_usd,
                        pol.id AS line_id
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON po.id = pol.order_id
                    JOIN product_product pp ON pp.id = pol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    WHERE po.state IN ('purchase', 'done')
                      AND (pol.display_type IS NULL OR pol.display_type NOT IN ('line_section', 'line_note'))
                )
                SELECT
                    row_number() OVER (ORDER BY p.date DESC, p.line_id) AS id,
                    p.date,
                    p.product_id,
                    p.partner_id,
                    p.categ_id,
                    cr.root_id AS main_categ_id,
                    COALESCE(cr.root_name, 'Sin Categoría') AS main_categ_name,
                    p.quantity,
                    p.price_total,
                    p.price_total_usd
                FROM consolidated_purchases p
                LEFT JOIN category_root_names cr ON cr.id = p.categ_id
            ) WITH DATA
        """.format(table=self._table))
        cr.execute(
            "CREATE UNIQUE INDEX {table}_id_uniq ON {table}(id)".format(table=self._table)
        )
        cr.execute(
            "CREATE INDEX {table}_date_idx ON {table}(date)".format(table=self._table)
        )
