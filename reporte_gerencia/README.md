# Reportes de Gerencia Consolidados

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-7C4DFF)](https://www.odoo.com/)
[![License](https://img.shields.io/badge/License-OEEL--1-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen)](#)

Dashboard gerencial con métricas consolidadas de POS, Ventas, Compras, Inventario y Cuentas por Cobrar/Pagar, soportado en vistas SQL materializadas y refrescadas por cron.

---

## ¿Qué resuelve?

Una gerencia necesita ver en una sola pantalla cuánto se vendió, cuánto costó, qué se compró, qué proveedor falló, cuánto hay en CxC/CxP y cómo se concentra el inventario por categoría. Sin este módulo, cada respuesta requiere cruzar POS, Ventas, Compras y Contabilidad a mano, con cálculos manuales de utilidad y conversión a USD.

Este módulo arma cuatro vistas materializadas (`MATERIALIZED VIEW`) en PostgreSQL que consolidan los datos de los orígenes más importantes (POS, ventas de oficina, facturas directas, compras y CxC/CxP) en columnas comparables, expresadas en moneda local y USD, agrupadas por **Categoría Principal** (la primera categoría raíz que no sea genérica como `ALL` / `Todos`).

## Características

- **Ventas Consolidadas** desde POS + Sale Orders + Facturas directas en una sola vista, con columnas de cantidad, venta total, costo total y utilidad (en Bs y USD).
- **Ranking de Proveedores** (compras) por monto USD, agrupable por categoría.
- **CxC y CxP** (estado financiero): detalle por contacto y tipo de cuenta.
- **Inventario ABC**: clasificación automática (A = 80 % del valor, B = 95 %, resto C) basada en valor de stock a costo.
- Tablero Spreadsheet publicado (`spreadsheet.dashboard`) con datos pre‑agregados.
- Cron cada 30 min que refresca las cuatro vistas materializadas concurrentemente.
- Vistas `pivot`, `graph` y `list` con filtros y agrupación nativa de Odoo (por mes, categoría principal, canal).
- Soporte multi‑moneda: tasa USD por documento (`tasa`, `x_tasa`, `currency_rate_ref`) con fallback a la última tasa de `res.currency.rate`.

## Arquitectura

```
reporte_gerencia/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── reporte_ventas_sql.py        # reporte.gerencia.ventas
│   ├── reporte_compras_sql.py       # reporte.gerencia.compras
│   ├── reporte_financiero_sql.py    # reporte.gerencia.financiero
│   ├── inventario_abc.py            # reporte.gerencia.inventario.abc
│   └── source_indexes.py
├── views/
│   └── reporte_gerencia_views.xml   # list, pivot, graph, search, menú
├── data/
│   ├── dashboard_gerencia.xml       # spreadsheet.dashboard publicado
│   ├── cron_refresh.xml             # Cron 30 min
│   └── files/
│       └── gerencia_dashboard.json  # Workbook spreadsheet
└── security/
    ├── security.xml                 # grupo "Gerente / Reportes"
    └── ir.model.access.csv
```

### Modelos / campos añadidos

Todas las vistas son **`_auto = False`** y crean una **`MATERIALIZED VIEW`** en PostgreSQL con la misma estructura de columnas:

| Modelo | Origen | Campos clave |
|---|---|---|
| `reporte.gerencia.ventas` | `pos_order_line ∪ sale_order_line ∪ account_move_line` | `date`, `source` (pos / sale / invoice), `product_id`, `categ_id`, `main_categ_name`, `quantity`, `price_total`, `price_total_usd`, `cost_total`, `cost_total_usd`, `margin`, `margin_usd`, `order_ref`, `order_count` |
| `reporte.gerencia.compras` | `purchase_order_line` (state `purchase`/`done`) | `date`, `partner_id`, `product_id`, `categ_id`, `main_categ_name`, `quantity`, `price_total`, `price_total_usd` |
| `reporte.gerencia.financiero` | `account_move_line` (CxC/CxP) | `date`, `partner_id`, `account_type` (asset_receivable / liability_payable), `invoiced_amount`, `paid_amount`, `balance`, duplicado en USD |
| `reporte.gerencia.inventario.abc` | `product_product` + `stock_quant` + `product_category` | `product_id`, `categ_id`, `main_categ_name`, `stock`, `cost`, `cost_usd`, `total_value`, `total_value_usd`, `cumulative_percentage`, `classification` (A/B/C) |

> La regla de **Categoría Principal** ignora nodos raíz cuyo nombre sea `ALL` / `All` / `Todos` y baja al primer hijo útil (`SPLIT_PART(parent_path, '/', 2)`).

Cada modelo implementa `_refresh_materialized_view()` que ejecuta:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY <tabla>;
```

> **Importante:** requiere que se haya creado previamente un índice único sobre `id` (sí, ya lo hace el `init()`).

### Dependencias

| Módulo | Razón |
|---|---|
| `base` | Modelo `res.company`, multi‑empresa |
| `sale` | `sale_order`, `sale_order_line` |
| `purchase` | `purchase_order`, `purchase_order_line` |
| `stock` | `stock_quant`, `stock_location` |
| `point_of_sale` | `pos_order`, `pos_order_line` |
| `account` | `account_move`, `account_move_line` |
| `spreadsheet_dashboard` | Publicación del tablero |
| `base_contable` | Campo `standard_price_usd` para inventario ABC |
| `pos_dual_currency` | `currency_rate_ref` en líneas de POS |
| `sale_margin` | `purchase_price` en líneas de venta |

## Instalación

```bash
cd $ODOO/addons
git clone git@github.com:lfcamarac/reporte_gerencia.git
./odoo-bin -u all -d <DB>
# Instalar "Reportes de Gerencia Consolidados" desde Apps
```

Las cuatro vistas materializadas se crean en `init()` del modelo correspondiente durante la instalación. El cron se activa automáticamente.

## Uso

### Menú

**Gerencia** (raíz) →

- **Ventas Consolidadas** (lista, pivot, gráfico)
- **Compras / Proveedores**
- **CxC y CxP**
- **Inventario ABC**

### Tablero pre‑armado

Buscar en *Spreadsheets → Tablero Gerencial*. El workbook está guardado en `data/files/gerencia_dashboard.json`.

### Refresco manual

Desde un shell de Odoo:

```python
env['reporte.gerencia.ventas']._refresh_materialized_view()
env['reporte.gerencia.compras']._refresh_materialized_view()
env['reporte.gerencia.financiero']._refresh_materialized_view()
env['reporte.gerencia.inventario.abc']._refresh_materialized_view()
```

O forzar la regeneración completa (DROP + CREATE) reinstalando el módulo.

### Permisos

El grupo `Gerencia → Gerente / Reportes` controla el acceso a todas las vistas. Asignar a usuarios gerenciales desde *Ajustes → Usuarios y Compañías → Usuarios*.

## Tests

```bash
./odoo-bin -d <DB> -i reporte_gerencia --test-enable --stop-after-init
```

El módulo no incluye tests propios; validar:

- Conteo de filas en cada `MATERIALIZED VIEW` ≥ 0 después de instalar.
- Cron activo en *Ajustes → Técnico → Acciones planificadas → "Reporte Gerencia: Refrescar vistas materializadas"*.
- Ejecución manual del cron → vuelve a refrescar sin errores.

## Glosario

- **Vista materializada (`MATERIALIZED VIEW`)**: snapshot físico en disco de una query; hay que refrescarlo manualmente o por cron para ver datos nuevos. Mucho más rápido que recomputar la query en cada load del list view.
- **REFRESH CONCURRENTLY**: requiere índice único sobre `id`; permite refrescar sin bloquear lecturas.
- **Categoría Principal**: nivel raíz "útil" del árbol de categorías; evita que categorías tipo `ALL / Todos` agrupen todo el inventario.
- **Inventario ABC**: clasificación clásica 80 / 95 / 5 (Pareto). A = alta inversión, B = media, C = baja.
- **`_auto = False`**: convención de Odoo para modelos respaldados por una vista SQL; no se crea tabla, el ORM lee columnas directamente.

## Autor y licencia

- **Autor:** Tecnosoft
- **Licencia:** OEEL‑1 (Odoo Enterprise EEAL License v1)
- **Versión Odoo:** 18.0