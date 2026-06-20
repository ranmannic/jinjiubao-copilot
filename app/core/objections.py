from __future__ import annotations

"""价格异议检测与受理回复。"""

OBJECTION_PATTERNS: dict[str, list[str]] = {
    "price_high": ["太贵", "价格高", "能不能便宜", "再低点", "折扣", "优惠"],
    "competition": ["别家", "竞品", "电商", "拼多多", "淘宝", "更便宜"],
    "quality": ["不好卖", "动销", "口感", "品质", "质量"],
    "trust": ["没听过", "品牌", "靠谱吗", "保障"],
    "policy": ["代理", "独家", "混批", "100件", "大批量", "账期"],
}


def detect_objection(text: str) -> str | None:
    lowered = text.lower()
    for kind, keywords in OBJECTION_PATTERNS.items():
        if any(k in lowered for k in keywords):
            return kind
    return None


def objection_reply(kind: str, product_name: str | None = None) -> str:
    name = product_name or "这款产品"
    replies = {
        "price_high": (
            f"理解您对价格的关注。{name}在常规批发政策下已留足零售毛利空间；"
            f"若您有稳定走量或组合进货计划，销售可评估阶梯价。"
            f"需要我帮您转销售谈具体折扣吗？"
        ),
        "competition": (
            "线上比价款和渠道专供款定位不同。我们主推线下控价、动销支持，"
            "避免客户拿去电商比价。您可以先小批量试销验证动销，再谈规模政策。"
        ),
        "quality": (
            "口感和动销是最实际的检验标准。建议先申请 1-2 箱样品或试销，"
            "我们可提供针对您渠道的话术和陈列建议。"
        ),
        "trust": (
            "进酒宝对入驻品牌有资质与供应链审核，并提供售后与物流保障。"
            "如需品牌授权书、检测报告等材料，销售可一并提供。"
        ),
        "policy": (
            "区域代理、混合批发、100件以上大批量及账期等，超出常规批发政策范围，"
            "需要销售经理根据您的身份和所在地单独审批。我这就帮您转接？"
        ),
    }
    return replies.get(kind, "收到您的顾虑，我可以帮您转销售详细解答。")
