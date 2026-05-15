# -*- coding: utf-8 -*-
{
    'name': 'Reportes de Gerencia Consolidados',
    'version': '18.0.1.0.0',
    'category': 'Tecnosoft/Gerencia',
    'summary': 'Dashboard gerencial con métricas consolidadas de POS, Ventas, Compras e Inventario.',
    'description': '''
        Módulo de Reportes de Gerencia para Farmatina.
        ============================================
        Permite visualizar en un solo tablero:
        - Ventas consolidadas (POS + Sale Orders).
        - Costo de Ventas y Utilidad Bruta.
        - Ticket Promedio.
        - Clasificación de Inventario (ABC).
        - Ranking de Proveedores.
        - Estado de CxC y CxP.
        - Agrupación por Categoría Principal de Producto.
    ''',
    'author': 'Tecnosoft',
    'website': 'https://tecnosoft.com.ve',
    'license': 'OEEL-1',
    'depends': [
        'base',
        'sale',
        'purchase',
        'stock',
        'point_of_sale',
        'account',
        'spreadsheet_dashboard',
        'base_contable',
        'pos_dual_currency',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/reporte_gerencia_views.xml',
        'data/dashboard_gerencia.xml',
    ],
    'installable': True,
    'application': True,
}
