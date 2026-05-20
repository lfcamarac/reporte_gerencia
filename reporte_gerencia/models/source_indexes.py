# -*- coding: utf-8 -*-
"""Índices funcionales en tablas fuente para acelerar las vistas gerenciales.

Se aplican via _register_hook al cargarse el módulo. Idempotentes: tools.create_index
no hace nada si el índice ya existe.
"""
from odoo import models, tools


class ReporteGerenciaSourceIndexes(models.AbstractModel):
    _name = 'reporte.gerencia.source.indexes'
    _description = 'Creación de índices en tablas fuente'

    def _register_hook(self):
        cr = self.env.cr
        # Account move line: facturas posted con producto
        tools.create_index(
            cr,
            'reporte_gerencia_aml_invoice_idx',
            'account_move_line',
            ['move_id', 'product_id'],
        )
        # POS order line por orden y producto
        tools.create_index(
            cr,
            'reporte_gerencia_pol_order_idx',
            'pos_order_line',
            ['order_id', 'product_id'],
        )
        # Sale order line por orden y producto
        tools.create_index(
            cr,
            'reporte_gerencia_sol_order_idx',
            'sale_order_line',
            ['order_id', 'product_id'],
        )
        # Purchase order line por orden y producto
        tools.create_index(
            cr,
            'reporte_gerencia_pol_purchase_idx',
            'purchase_order_line',
            ['order_id', 'product_id'],
        )
        # Stock quant por producto y location (para inventario ABC)
        tools.create_index(
            cr,
            'reporte_gerencia_quant_loc_idx',
            'stock_quant',
            ['product_id', 'location_id'],
        )
        # pos_order.account_move para NOT EXISTS de facturas directas
        tools.create_index(
            cr,
            'reporte_gerencia_po_account_move_idx',
            'pos_order',
            ['account_move'],
        )
        return super()._register_hook()
