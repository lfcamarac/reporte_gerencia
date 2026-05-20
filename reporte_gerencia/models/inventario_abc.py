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

    @api.model
    def _refresh_materialized_view(self):
        self.env.cr.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY %s" % self._table
        )

    def init(self):
        cr = self.env.cr
        cr.execute("DROP MATERIALIZED VIEW IF EXISTS %s CASCADE" % self._table)
        cr.execute("DROP VIEW IF EXISTS %s CASCADE" % self._table)
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
                product_stock AS (
                    SELECT
                        sq.product_id,
                        SUM(sq.quantity) AS quantity
                    FROM stock_quant sq
                    JOIN stock_location sl ON sl.id = sq.location_id
                    WHERE sl.usage = 'internal'
                    GROUP BY sq.product_id
                ),
                product_values AS (
                    SELECT
                        pp.id AS product_id,
                        pt.categ_id AS categ_id,
                        COALESCE(ps.quantity, 0) AS stock,
                        COALESCE((pp.standard_price->>'{company_id}')::numeric, 0) AS cost,
                        COALESCE(pt.standard_price_usd, 0) AS cost_usd,
                        COALESCE(ps.quantity, 0) * COALESCE((pp.standard_price->>'{company_id}')::numeric, 0) AS total_value,
                        COALESCE(ps.quantity, 0) * COALESCE(pt.standard_price_usd, 0) AS total_value_usd
                    FROM product_product pp
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    LEFT JOIN product_stock ps ON ps.product_id = pp.id
                    WHERE (pt.is_storable = True OR pt.type = 'product')
                      AND pt.active = True
                ),
                total_inv AS (
                    SELECT SUM(total_value_usd) AS grand_total FROM product_values
                ),
                calculated_abc AS (
                    SELECT
                        pv.*,
                        COALESCE(cr.root_name, 'Sin Categoría') AS main_categ_name,
                        ti.grand_total,
                        SUM(pv.total_value_usd) OVER (ORDER BY pv.total_value_usd DESC, pv.product_id ASC) AS cumulative_value
                    FROM product_values pv
                    CROSS JOIN total_inv ti
                    LEFT JOIN category_root_names cr ON cr.id = pv.categ_id
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
            ) WITH DATA
        """.format(table=self._table, company_id=company_id))
        cr.execute(
            "CREATE UNIQUE INDEX {table}_id_uniq ON {table}(id)".format(table=self._table)
        )
        cr.execute(
            "CREATE INDEX {table}_classification_idx ON {table}(classification)".format(table=self._table)
        )
