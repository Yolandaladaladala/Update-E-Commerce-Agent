from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
from llm import chat

@dataclass
class RouteDecision:
    module: str
    reason: str

def route_request(user_text: str) -> RouteDecision:
    t = user_text.lower()

    finance_words = ["profit", "利润", "roas", "成本", "finance", "财务", "gmv", "margin", "roi"]
    marketing_words = ["creator", "达人", "kol", "koc", "marketing", "campaign", "直播", "内容", "网红"]
    ops_words = ["listing", "sku", "上架", "库存", "订单", "operation", "店铺", "葡语", "本地化"]
    market_words = ["market", "市场", "research", "竞品", "价格带", "进入", "机会", "类目"]

    if any(x in t for x in finance_words):
        return RouteDecision("finance", "The request is about financial/performance analysis.")
    if any(x in t for x in marketing_words):
        return RouteDecision("marketing", "The request is about creator/content/campaign operations.")
    if any(x in t for x in ops_words):
        return RouteDecision("operations", "The request is about listing/commerce operations.")
    if any(x in t for x in market_words):
        return RouteDecision("market", "The request is about market/product intelligence.")
    return RouteDecision("market", "Default to market discovery when intent is ambiguous.")

def explain_route(user_text: str) -> str:
    d = route_request(user_text)
    return chat(
        f"""The user said: {user_text}
The deterministic router selected module: {d.module}
Reason: {d.reason}
Explain in 2-4 short sentences what the system would do next and what minimum input is needed."""
    )
