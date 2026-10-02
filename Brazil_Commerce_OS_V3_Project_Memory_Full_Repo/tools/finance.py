from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Iterable, Optional

import pandas as pd


# =========================================================
# Finance field aliases
# =========================================================
# Goal:
# - accept messy merchant files with common real-world column names;
# - map them into a stable internal finance schema;
# - never silently treat a missing field as zero.
#
# IMPORTANT:
# "cost" is mapped to product_cost here because the current test file uses
# row-level total product cost. If in another merchant file "cost" means unit
# cost, the mapping should be confirmed before using it for profitability.
FIELD_ALIASES: Dict[str, list[str]] = {
    # Sales / deductions
    "revenue": [
        "revenue",
        "sales",
        "gmv",
        "gross_sales",
        "gross_revenue",
        "sales_amount",
        "order_revenue",
        "paid_amount",
        "payment_amount",
        "net_sales",
    ],
    "discounts": [
        "discounts",
        "discount",
        "discount_amount",
        "promotion_discount",
        "voucher_discount",
    ],
    "refunds": [
        "refunds",
        "refund",
        "refund_amount",
        "refunded_amount",
        "return_amount",
    ],

    # Variable costs
    "platform_fee": [
        "platform_fee",
        "platform_fees",
        "transaction_fee",
        "commission_fee",
        "marketplace_fee",
        "service_fee",
    ],
    "product_cost": [
        "product_cost",
        "cogs",
        "cost_of_goods_sold",
        "goods_cost",
        "merchandise_cost",
        "cost",
    ],
    "logistics_cost": [
        "logistics_cost",
        "shipping_cost",
        "delivery_cost",
        "freight_cost",
        "fulfilment_cost",
        "fulfillment_cost",
        "warehouse_shipping_cost",
    ],
    "ad_spend": [
        "ad_spend",
        "advertising_spend",
        "advertising_cost",
        "ads_cost",
        "ad_cost",
        "media_spend",
        "marketing_spend",
    ],
    "creator_cost": [
        "creator_cost",
        "creator_fee",
        "creator_fees",
        "kol_cost",
        "kol_fee",
        "influencer_cost",
        "influencer_fee",
        "affiliate_cost",
        "affiliate_fee",
        "creator_commission",
    ],
    "software_cost": [
        "software_cost",
        "ai_cost",
        "livestream_cost",
        "tool_cost",
        "saas_cost",
    ],
    "tax": [
        "tax",
        "tax_cost",
        "tax_expense",
        "tax_amount",
        "taxes",
    ],

    # Order / funnel fields
    "order_id": [
        "order_no",
        "order_id",
        "order_number",
        "order",
        "transaction_id",
    ],
    "order_count": [
        "orders",
        "order_count",
        "number_of_orders",
    ],
    "quantity": [
        "quantity",
        "qty",
        "units",
        "units_sold",
        "item_quantity",
    ],
    "visits": [
        "visits",
        "sessions",
        "traffic",
    ],
    "clicks": [
        "clicks",
        "product_clicks",
        "link_clicks",
    ],
    "impressions": [
        "impressions",
        "views",
        "ad_impressions",
    ],

    # Useful dimensions
    "date": [
        "date",
        "order_date",
        "transaction_date",
    ],
    "product": [
        "product",
        "product_name",
        "sku_name",
        "item_name",
    ],
    "sku": [
        "sku",
        "sku_id",
        "product_sku",
    ],
    "platform": [
        "platform",
        "marketplace",
        "channel",
    ],
    "currency": [
        "currency",
        "currency_code",
    ],
}


# =========================================================
# File loading
# =========================================================
def load_finance_file(file_obj) -> pd.DataFrame:
    """
    Load CSV / XLSX / XLS / JSON into a DataFrame.

    Streamlit UploadedFile objects expose .name and can be read directly.
    """
    name = getattr(file_obj, "name", "").lower()

    if name.endswith(".csv"):
        df = pd.read_csv(file_obj)

    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_obj)

    elif name.endswith(".json"):
        data = pd.read_json(file_obj)
        df = data

    else:
        raise ValueError("Unsupported finance file. Please upload CSV, XLSX, XLS or JSON.")

    if df is None or df.empty:
        raise ValueError("The uploaded finance file contains no readable rows.")

    return _normalise_columns(df)


# =========================================================
# Normalisation helpers
# =========================================================
def _normalise_name(name: Any) -> str:
    return (
        str(name)
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [_normalise_name(c) for c in out.columns]
    return out


def _first_existing(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    column_set = set(columns)
    for candidate in candidates:
        candidate = _normalise_name(candidate)
        if candidate in column_set:
            return candidate
    return None


def _build_mapping(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    columns = list(df.columns)
    mapping: Dict[str, Optional[str]] = {}

    for canonical, aliases in FIELD_ALIASES.items():
        mapping[canonical] = _first_existing(columns, aliases)

    return mapping


def _to_numeric(series: pd.Series) -> pd.Series:
    """
    Convert common finance values such as:
    299
    '299'
    'R$ 299.00'
    '$1,200.50'
    into numeric values.

    Invalid values become NaN rather than zero.
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = (
        series.astype(str)
        .str.replace(r"[^\d\-,.()]", "", regex=True)
        .str.replace(",", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .replace("", pd.NA)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _sum_numeric(df: pd.DataFrame, column: Optional[str]) -> Optional[float]:
    """
    Return None when the field does not exist or has no numeric observations.

    This is important:
    missing field != zero.
    """
    if not column or column not in df.columns:
        return None

    values = _to_numeric(df[column])
    valid = values.dropna()

    if valid.empty:
        return None

    return float(valid.sum())


def _count_orders(df: pd.DataFrame, mapping: Dict[str, Optional[str]]) -> Optional[int]:
    """
    Prefer a stable order ID and count unique orders.

    If no order ID exists, fall back to an explicit order_count field.
    We intentionally do NOT assume row count = order count because one order
    can contain multiple lines/SKUs.
    """
    order_id_col = mapping.get("order_id")
    if order_id_col and order_id_col in df.columns:
        values = df[order_id_col].dropna().astype(str).str.strip()
        values = values[values != ""]
        if not values.empty:
            return int(values.nunique())

    order_count_col = mapping.get("order_count")
    if order_count_col and order_count_col in df.columns:
        value = _sum_numeric(df, order_count_col)
        if value is not None:
            return int(value)

    return None


def _availability(mapping: Dict[str, Optional[str]]) -> Dict[str, bool]:
    return {key: bool(value) for key, value in mapping.items()}


# =========================================================
# Main deterministic finance engine
# =========================================================
def analyse_finance(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Deterministic finance analysis.

    Design principles:
    1. map messy merchant column names into a stable internal schema;
    2. missing is NOT zero;
    3. count unique order IDs for AOV when possible;
    4. Python calculates; the LLM only explains the returned result.
    """
    if df is None or df.empty:
        raise ValueError("Finance data is empty.")

    df = _normalise_columns(df)
    mapping = _build_mapping(df)
    available = _availability(mapping)

    # -----------------------------------------------------
    # Required top-line sales
    # -----------------------------------------------------
    revenue = _sum_numeric(df, mapping.get("revenue"))

    if revenue is None:
        raise ValueError(
            "Missing sales/revenue/GMV. "
            "The finance engine could not identify a usable revenue field."
        )

    # -----------------------------------------------------
    # Sales deductions
    # -----------------------------------------------------
    discounts = _sum_numeric(df, mapping.get("discounts"))
    refunds = _sum_numeric(df, mapping.get("refunds"))

    # For Net Sales:
    # an absent deduction is NOT claimed to be observed zero.
    # We calculate an available net-sales view using known deductions,
    # while exposing availability flags and missing fields separately.
    known_discounts = discounts if discounts is not None else 0.0
    known_refunds = refunds if refunds is not None else 0.0
    net_sales = revenue - known_discounts - known_refunds

    # -----------------------------------------------------
    # Costs
    # -----------------------------------------------------
    platform_fee = _sum_numeric(df, mapping.get("platform_fee"))
    product_cost = _sum_numeric(df, mapping.get("product_cost"))
    logistics_cost = _sum_numeric(df, mapping.get("logistics_cost"))
    ad_spend = _sum_numeric(df, mapping.get("ad_spend"))
    creator_cost = _sum_numeric(df, mapping.get("creator_cost"))
    software_cost = _sum_numeric(df, mapping.get("software_cost"))
    tax = _sum_numeric(df, mapping.get("tax"))

    # -----------------------------------------------------
    # Order / volume metrics
    # -----------------------------------------------------
    order_count = _count_orders(df, mapping)
    quantity = _sum_numeric(df, mapping.get("quantity"))

    aov = None
    if order_count and order_count > 0:
        # Keep V3 convention: AOV uses Gross Sales / Orders.
        aov = revenue / order_count

    # -----------------------------------------------------
    # Marketing metrics
    # -----------------------------------------------------
    roas = None
    if ad_spend is not None and ad_spend > 0:
        # Keep V3 convention: ROAS = Gross Sales / Ad Spend.
        roas = revenue / ad_spend

    visits = _sum_numeric(df, mapping.get("visits"))
    clicks = _sum_numeric(df, mapping.get("clicks"))
    impressions = _sum_numeric(df, mapping.get("impressions"))

    conversion_rate = None
    if visits is not None and visits > 0 and order_count is not None:
        conversion_rate = order_count / visits

    ctr = None
    if impressions is not None and impressions > 0 and clicks is not None:
        ctr = clicks / impressions

    # -----------------------------------------------------
    # Gross profit
    # -----------------------------------------------------
    gross_profit = None
    gross_margin = None

    if product_cost is not None:
        gross_profit = net_sales - product_cost
        if net_sales != 0:
            gross_margin = gross_profit / net_sales

    # -----------------------------------------------------
    # Contribution profitability
    # -----------------------------------------------------
    # These fields are considered critical for the current ecommerce
    # contribution-profit definition.
    #
    # NOTE:
    # creator_cost remains "missing" when the file does not tell us whether
    # creator activity existed. We do NOT silently assume zero.
    critical_costs = {
        "product_cost": product_cost,
        "logistics_cost": logistics_cost,
        "ad_spend": ad_spend,
        "creator_cost": creator_cost,
    }

    missing_for_profitability = [
        field for field, value in critical_costs.items() if value is None
    ]

    # Optional/conditional fields are included when observed.
    known_costs = {
        "platform_fee": platform_fee,
        "product_cost": product_cost,
        "logistics_cost": logistics_cost,
        "ad_spend": ad_spend,
        "creator_cost": creator_cost,
        "software_cost": software_cost,
        "tax": tax,
    }

    known_cost_total = sum(
        value for value in known_costs.values() if value is not None
    )

    contribution_profit = None
    contribution_margin = None

    if not missing_for_profitability:
        contribution_profit = net_sales - known_cost_total
        if net_sales != 0:
            contribution_margin = contribution_profit / net_sales

    # Even when full profitability is incomplete, it is useful to show the
    # current known-cost subtotal without pretending it is final profit.
    profit_before_unconfirmed_costs = net_sales - known_cost_total

    # -----------------------------------------------------
    # Supporting rates
    # -----------------------------------------------------
    platform_fee_rate = None
    if platform_fee is not None and net_sales != 0:
        platform_fee_rate = platform_fee / net_sales

    logistics_cost_rate = None
    if logistics_cost is not None and net_sales != 0:
        logistics_cost_rate = logistics_cost / net_sales

    refund_rate_value = None
    if refunds is not None and revenue != 0:
        # Value-based refund rate, explicitly not order-based.
        refund_rate_value = refunds / revenue

    # -----------------------------------------------------
    # Missing / quality controls
    # -----------------------------------------------------
    missing_fields = [
        canonical
        for canonical, source_col in mapping.items()
        if source_col is None
    ]

    data_quality_notes: list[str] = []

    if mapping.get("product_cost") == "cost":
        data_quality_notes.append(
            "Column 'cost' was mapped to product_cost. "
            "Confirm that it represents total row-level product cost rather than unit cost."
        )

    if mapping.get("revenue") == "net_sales":
        data_quality_notes.append(
            "Column 'net_sales' was used as the revenue source. "
            "Do not subtract refunds/discounts again if that field is already net of deductions."
        )

    if discounts is None:
        data_quality_notes.append(
            "No discount field was supplied. Net Sales currently subtracts only observed deductions."
        )

    if creator_cost is None:
        data_quality_notes.append(
            "Creator cost is not supplied. Confirm whether creator/KOL activity was absent (true zero) "
            "or the cost is simply unavailable."
        )

    # -----------------------------------------------------
    # Return structure expected by app.py
    # -----------------------------------------------------
    return {
        # Existing V3 keys used by app.py
        "net_sales": net_sales,
        "aov": aov,
        "roas": roas,
        "contribution_profit": contribution_profit,
        "contribution_margin": contribution_margin,
        "missing_for_profitability": missing_for_profitability,
        "mapping": mapping,

        # Additional professional finance outputs
        "gross_sales": revenue,
        "discounts": discounts,
        "refunds": refunds,
        "order_count": order_count,
        "quantity": quantity,

        "product_cost": product_cost,
        "platform_fee": platform_fee,
        "logistics_cost": logistics_cost,
        "ad_spend": ad_spend,
        "creator_cost": creator_cost,
        "software_cost": software_cost,
        "tax": tax,

        "gross_profit": gross_profit,
        "gross_margin": gross_margin,
        "platform_fee_rate": platform_fee_rate,
        "logistics_cost_rate": logistics_cost_rate,
        "refund_rate_value": refund_rate_value,

        "visits": visits,
        "clicks": clicks,
        "impressions": impressions,
        "conversion_rate": conversion_rate,
        "ctr": ctr,

        "known_cost_total": known_cost_total,
        "profit_before_unconfirmed_costs": profit_before_unconfirmed_costs,

        "availability": available,
        "missing_fields": missing_fields,
        "data_quality_notes": data_quality_notes,

        "row_count": int(len(df)),
    }


# Section 4 update: completeness-aware parsing and calculation.
_legacy_analyse = analyse_finance

def _normalise_name(name):
    import re
    s = str(name).strip()
    match = re.search(r'\(([a-z_]+)\)\s*$', s)
    if match:
        return match.group(1)
    return s.lower().replace('-', '_').replace('/', '_').replace(' ', '_')

def _to_numeric(series):
    import re
    def parse(v):
        if pd.isna(v): return float('nan')
        if isinstance(v, (int, float)): return float(v)
        s = re.sub(r'[^0-9,.()\-]', '', str(v).strip())
        if not s: return float('nan')
        if s.startswith('(') and s.endswith(')'): s = '-' + s[1:-1]
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
        elif ',' in s:
            parts = s.split(',')
            s = s.replace(',', '.') if len(parts) == 2 and len(parts[-1]) in (1, 2) else s.replace(',', '')
        elif s.count('.') > 1: s = s.replace('.', '')
        try: return float(s)
        except ValueError: return float('nan')
    return series.map(parse)

def analyse_finance(df, price_basis='total', cost_basis='total', confirmed_zero=None):
    x = _normalise_columns(df)
    confirmed_zero = set(confirmed_zero or [])
    mapping = _build_mapping(x)
    if not mapping['revenue']:
        price = _first_existing(x.columns, ['price', 'selling_price', '成交价', '售价'])
        if price:
            values = _to_numeric(x[price])
            if price_basis == 'unit':
                q = mapping.get('quantity')
                if not q: raise ValueError('单价需要 quantity/qty 列；请提供数量或选择订单总额。')
                values = values * _to_numeric(x[q])
            x['revenue'] = values
    mapping = _build_mapping(x)
    if cost_basis == 'unit' and mapping.get('product_cost'):
        q = mapping.get('quantity')
        if not q: raise ValueError('单件成本需要数量列。')
        x['product_cost'] = _to_numeric(x[mapping['product_cost']]) * _to_numeric(x[q])
    for field in confirmed_zero:
        col = _build_mapping(x).get(field)
        if not col: x[field] = 0.0
        # An explicit whole-field zero does not fill partially missing columns.
    mapping = _build_mapping(x)
    rev_col = mapping.get('revenue')
    if not rev_col: raise ValueError('未识别成交金额；需要 revenue/sales/GMV/price。')
    if _to_numeric(x[rev_col]).isna().any():
        raise ValueError('成交金额存在空白或无法解析的值，请修正后再算总收入。')
    # Already-net revenue must not have deductions subtracted a second time.
    already_net = rev_col == 'net_sales'
    if already_net:
        for field in ('discounts', 'refunds'):
            col = mapping.get(field)
            if col: x[col] = 0.0
    calc = _legacy_analyse(x)
    quality = []
    required = ['product_cost','platform_fee','logistics_cost','ad_spend','creator_cost','tax']
    if not already_net: required += ['discounts','refunds']
    numeric = {}
    for field in ['revenue'] + required + ['software_cost']:
        col = mapping.get(field)
        vals = _to_numeric(x[col]) if col else pd.Series(float('nan'), index=x.index)
        numeric[field] = vals
        missing = int(vals.isna().sum())
        quality.append({'field':field,'source_column':col or '', 'known_rows':len(x)-missing,'missing_rows':missing,'known_subtotal':float(vals.sum()) if vals.notna().any() else None})
    missing = [r['field'] for r in quality if r['field'] in required and r['missing_rows']]
    calc['missing_for_profitability'] = missing
    calc['contribution_profit'] = None
    calc['contribution_margin'] = None
    if not missing:
        cp = calc['net_sales'] - sum(float(numeric[f].sum()) for f in required if f not in ('discounts','refunds'))
        calc['contribution_profit'] = cp
        calc['contribution_margin'] = cp / calc['net_sales'] if calc['net_sales'] else None
    calc['net_sales_complete'] = already_net or not any(f in missing for f in ['discounts','refunds'])
    calc['quality'] = quality
    calc['roas'] = None # No attributed revenue: total store sales is not ad ROAS.
    calc['data_quality_notes'].append('ROAS未计算：需要广告归因收入，不能用全店销售额代替。')
    if already_net: calc['data_quality_notes'].append('输入为net_sales，已阻止重复扣减；不将该值称为毛销售额。')
    if missing: calc['data_quality_notes'].append('缺失项或部分空值未当成零；已知成本余额不是完整利润。')
    net = numeric['revenue'].copy()
    if not already_net:
        for f in ['discounts','refunds']: net = net - numeric[f]
    gross = net - numeric['product_cost']
    calc['gross_profit'] = float(gross.sum()) if gross.notna().all() else None
    calc['gross_margin'] = calc['gross_profit']/calc['net_sales'] if calc['gross_profit'] is not None and calc['net_sales'] else None
    calc['gross_profit_known_rows'] = int(gross.notna().sum())
    detail = x.copy()
    detail['net_sales_calculated'] = net
    detail['gross_profit_calculated'] = gross
    detail['contribution_calculated'] = net.copy()
    for f in ['product_cost','platform_fee','logistics_cost','ad_spend','creator_cost','tax']:
        detail['contribution_calculated'] -= numeric[f]
    calc['detail'] = detail
    calc['currency'] = str(x[mapping['currency']].dropna().iloc[0]) if mapping.get('currency') and x[mapping['currency']].notna().any() else '未提供'
    calc['group_analysis'] = {}
    for dim in ['platform','sku']:
        col=mapping.get(dim)
        if col:
            groups=[]
            for key,g in detail.groupby(col,dropna=False):
                r={'group':str(key),'rows':len(g)}
                for f in ['net_sales_calculated','gross_profit_calculated','contribution_calculated']:
                    r[f]=float(g[f].sum()) if g[f].notna().all() else None
                groups.append(r)
            calc['group_analysis'][dim]=groups
    return calc

