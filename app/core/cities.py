from __future__ import annotations

"""快捷城市选择。"""

CITY_OPTIONS = [
    "北京市", "上海市", "广州市", "深圳市", "杭州市", "南京市", "苏州市",
    "成都市", "重庆市", "武汉市", "西安市", "郑州市", "长沙市", "合肥市",
    "宁波市", "温州市", "厦门市", "青岛市", "济南市", "天津市", "其他",
]


def city_quick_replies(prefix: str = "city") -> list[tuple[str, str]]:
    return [(f"{prefix}_{i}", c) for i, c in enumerate(CITY_OPTIONS)]
