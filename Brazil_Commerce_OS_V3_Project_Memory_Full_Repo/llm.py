from __future__ import annotations
import requests
from typing import Optional
from config import LLM_API_URL, LLM_API_KEY, LLM_MODEL, DEMO_MODE

SYSTEM = """You are the Brazil Commerce OS business copilot.
Be analytical, operational, source-aware, and explicit about uncertainty.

Rules:
- Never invent creator identities.
- Never invent certifications, inventory, prices, platform fees, market share, sales, or financial numbers.
- Missing data must remain missing.
- Deterministic calculations are provided by tools; do not recalculate them freely.
- Distinguish verified/observed/user-provided/estimated/inferred information.
- For high-impact actions (contracts, publishing, payments, compliance), require human approval.
"""


def demo_answer(prompt: str) -> str:
    p = prompt.lower()
    if "finance" in p or "profit" in p or "roas" in p:
        return (
            "Demo AI：先看数据完整性，再解释结果。"
            "ROAS 只能说明广告收入效率，不等于利润；Contribution Profit 需要真实成本。"
            "若 product_cost / logistics / ad_spend / creator_cost 缺失，系统应显示 Profitability = Incomplete。"
        )
    if "creator" in p or "达人" in p or "kol" in p:
        return (
            "Demo AI：Creator 必须来自真实来源（平台、FastMoss/外部分析、客户 CRM、用户上传文件）。"
            "AI 可以做 fit ranking、解释原因和生成 brief，但不能凭空创造达人或报价。"
        )
    if "operation" in p or "listing" in p or "sku" in p:
        return (
            "Demo AI：Operations 可以生成 Listing/translation，但只能基于 Approved Product Facts。"
            "认证、库存、价格、退货政策、平台费用必须来自真实数据或规则表。"
        )
    if "market" in p or "research" in p or "市场" in p:
        return (
            "Demo AI：Market Research 应先定义 research dimensions，再检索证据。"
            "关键数字要记录 source/date/geography/definition；没有可靠数据时返回 insufficient evidence。"
        )
    return (
        "Demo AI：我会把你的问题先归到 Market / Operations / Marketing / Finance，"
        "再说明需要哪些输入、哪些信息缺失、下一步应该调用什么工具。"
    )


def chat(
    prompt: str,
    system: Optional[str] = None,
    *,
    max_tokens: int = 1200,
    temperature: float = 0.2,
) -> str:
    """OpenAI-compatible chat call with per-task output controls.

    Market Research V2 uses a larger max_tokens value so the report is not
    artificially capped at a short memo. Other modules can keep smaller limits.
    """
    if DEMO_MODE:
        return demo_answer(prompt)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system or SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    r = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]
