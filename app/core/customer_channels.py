from __future__ import annotations

from app.models.domain import ChannelScene, CustomerProfile, CustomerType


def infer_channels_from_type(profile: CustomerProfile) -> None:
    """根据业态自动推断主渠道，减少多余问询。"""
    if profile.channels or profile.channel_mode:
        return
    mapping: dict[CustomerType, tuple[list[ChannelScene], str | None]] = {
        CustomerType.PREMIUM_WINE_SHOP: ([ChannelScene.RETAIL, ChannelScene.GROUP_PURCHASE], "mixed"),
        CustomerType.DEALER: ([], "wholesale"),
        CustomerType.IMPORTER: ([], "wholesale"),
        CustomerType.RETAIL_CONVENIENCE: ([ChannelScene.RETAIL], "retail"),
        CustomerType.CORPORATE_GIFT: ([ChannelScene.GROUP_PURCHASE, ChannelScene.CORPORATE_GIFT], "group"),
        CustomerType.ONLINE_ECOMMERCE: ([ChannelScene.ONLINE_DISTRIBUTION], "online"),
        CustomerType.RESTAURANT: ([ChannelScene.RESTAURANT_PAIRING, ChannelScene.BANQUET], "banquet"),
        CustomerType.CLUB_BAR: ([ChannelScene.RESTAURANT_PAIRING], "banquet"),
        CustomerType.PERSONAL_USE: ([ChannelScene.RETAIL], "retail"),
    }
    channels, mode = mapping.get(profile.customer_type, ([], None))
    for ch in channels:
        if ch not in profile.channels:
            profile.channels.append(ch)
    if mode:
        profile.channel_mode = mode
