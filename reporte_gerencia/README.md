# Módulo de Reportes de Gerencia Consolidados (Farmatina)

Este módulo proporciona una visión analítica de 360 grados sobre el desempeño del negocio en Odoo 18. Centraliza datos de múltiples fuentes (Punto de Venta, Ventas de Oficina, Compras e Inventario) mediante vistas SQL optimizadas y un Dashboard nativo de Odoo Spreadsheet.

## Características Principales

### 1. Análisis de Ventas y Rentabilidad
*   **Fuentes de Datos:** Consolida pedidos de POS (`pos.order`), pedidos de venta (`sale.order`) y facturas directas (`account.move`).
*   **Precisión de Margen:** Todos los cálculos de utilidad se basan en la **Base Imponible (Neto)**, excluyendo impuestos para reflejar la realidad contable.
*   **Multimoneda:** Maneja montos en Bs y USD. Prioriza la tasa registrada en el documento y utiliza la última tasa del BCV como respaldo (fallback).
*   **Categorización Inteligente:** Utiliza la jerarquía de categorías de producto para agrupar por "Categoría Principal", ignorando raíces genéricas como "ALL" para mostrar segmentaciones reales (Medicamentos, Misceláneos, etc.).

### 2. Clasificación de Inventario ABC
*   **Lógica:** Clasifica los productos según su valor de inversión actual (Existencia x Costo).
    *   **Clase A (80%):** Productos que representan el 80% del valor del inventario (Alta Inversión).
    *   **Clase B (15%):** Productos que representan el siguiente 15% del valor.
    *   **Clase C (5%):** El resto de productos con baja incidencia financiera.
*   **Actualización:** Se recalcula automáticamente cada 30 minutos vía cron.

### 3. Gestión Financiera (CxC / CxP)
*   Visualización consolidada de saldos pendientes por cobrar y por pagar.
*   Permite filtrar por contacto para identificar rápidamente a los mayores deudores o acreedores.

### 4. Tablero Gerencial (Spreadsheet Dashboard)
*   **KPIs Críticos:** Venta Total, Costo, Utilidad, Margen % y Ticket Promedio.
*   **Comparativas:** Indicadores de variación mensual automática.
*   **Filtros Globales:** Capacidad de filtrar todo el tablero por rango de fechas, categorías de producto y canal de venta.

## Aspectos Técnicos

### Vistas Materializadas
Para garantizar un rendimiento óptimo, el módulo utiliza **Vistas Materializadas** en PostgreSQL. Esto permite que el Dashboard cargue instantáneamente incluso con volúmenes masivos de datos.

*   **Refresco de Datos:** El cron `cron_refresh_reporte_gerencia` actualiza las vistas cada 30 minutos.
*   **Acción Manual:** Los gerentes pueden forzar la actualización desde el menú de Tareas Programadas si es necesario.

### Seguridad
*   El acceso está restringido al grupo **Gerente / Reportes**. Solo los usuarios en este grupo pueden ver el menú "Gerencia" y acceder a la información de costos y utilidades.

## Instalación y Actualización
Para aplicar cambios en el servidor:
```bash
cd /var/odoo/farmatina && sudo -u odoo venv/bin/python3 src/odoo-bin -c odoo.conf --no-http --stop-after-init --update reporte_gerencia
```

---
**Desarrollado por:** Tecnosoft
**Soporte:** https://tecnosoft.com.ve
