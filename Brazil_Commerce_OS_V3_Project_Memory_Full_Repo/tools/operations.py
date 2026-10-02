from __future__ import annotations
from typing import Dict, Any
from llm import chat

def run_operations(
    merchant_id: str,
    product_id: str,
    sku: str,
    product_name: str,
    platform: str,
    approved_facts: str,
    selling_price: str = "",
    inventory: str = "",
    unit_cost: str = "",
) -> Dict[str, Any]:
    missing = []
    if not selling_price:
        missing.append("selling_price")
    if not inventory:
        missing.append("inventory")
    if not unit_cost:
        missing.append("unit_cost")

    prompt = f"""
You are the E-commerce Operations tool for Brazil.

Merchant ID: {merchant_id}
Product ID: {product_id}
SKU: {sku}
Product: {product_name}
Platform: {platform}

APPROVED PRODUCT FACTS:
{approved_facts}

OPTIONAL REAL DATA:
selling_price={selling_price or "missing"}
inventory={inventory or "missing"}
unit_cost={unit_cost or "missing"}

Generate:
1. Brazilian Portuguese listing title
2. 4-6 bullet points based ONLY on approved facts
3. short product description
4. launch checklist
5. missing-data warnings

Never invent:
- certifications
- health/performance claims
- materials
- inventory
- price
- platform fees
- refund policy
"""
    copy = chat(prompt)

    return {
        "merchant_id": merchant_id,
        "product_id": product_id,
        "sku": sku,
        "product_name": product_name,
        "platform": platform,
        "missing": missing,
        "generated_pack": copy,
    }
