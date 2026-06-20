from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConversationPhase(str, Enum):
    WELCOME = "welcome"
    TYPE_IDENTIFICATION = "type_identification"
    INQUIRY = "inquiry"
    CHANNEL_DISCOVERY = "channel_discovery"
    NEED_DISCOVERY = "need_discovery"
    RECOMMENDATION = "recommendation"
    PRICE_POLICY = "price_policy"
    OBJECTION = "objection"
    BUSINESS_PLAN = "business_plan"
    HANDOFF = "handoff"
    CLOSED = "closed"


class StoreType(str, Enum):
    NONE = "none"
    PREMIUM_WINE_SHOP = "premium_wine_shop"
    RETAIL_CONVENIENCE = "retail_convenience"
    CLUB = "club"
    RESTAURANT_BAR = "restaurant_bar"
    SUPERMARKET = "supermarket"
    OTHER = "other"


STORE_TYPE_LABELS: Dict[StoreType, str] = {
    StoreType.NONE: "无实体门店",
    StoreType.PREMIUM_WINE_SHOP: "名烟名酒",
    StoreType.RETAIL_CONVENIENCE: "烟酒便利零售店",
    StoreType.CLUB: "会所",
    StoreType.RESTAURANT_BAR: "餐厅/酒吧/酒馆",
    StoreType.SUPERMARKET: "超市/连锁商超",
    StoreType.OTHER: "其他",
}


class CustomerType(str, Enum):
    DEALER = "dealer"
    IMPORTER = "importer"
    PREMIUM_WINE_SHOP = "premium_wine_shop"
    RETAIL_CONVENIENCE = "retail_convenience"
    RESTAURANT = "restaurant"
    CLUB_BAR = "club_bar"
    CORPORATE_GIFT = "corporate_gift"
    UNKNOWN = "unknown"


class ChannelScene(str, Enum):
    GROUP_PURCHASE = "group_purchase"
    RETAIL = "retail"
    BANQUET = "banquet"
    RESTAURANT_PAIRING = "restaurant_pairing"
    CORPORATE_GIFT = "corporate_gift"
    ONLINE_DISTRIBUTION = "online_distribution"
    MIXED = "mixed"


CUSTOMER_TYPE_LABELS: Dict[CustomerType, str] = {
    CustomerType.DEALER: "经销商/批发商",
    CustomerType.IMPORTER: "进口商/贸易公司",
    CustomerType.PREMIUM_WINE_SHOP: "高端烟酒店",
    CustomerType.RETAIL_CONVENIENCE: "中低端烟酒店/杂货便利店",
    CustomerType.RESTAURANT: "餐厅/酒店",
    CustomerType.CLUB_BAR: "会所/KTV/酒吧",
    CustomerType.CORPORATE_GIFT: "企业团购/礼品公司",
    CustomerType.UNKNOWN: "未明确",
}

CHANNEL_SCENE_LABELS: Dict[ChannelScene, str] = {
    ChannelScene.GROUP_PURCHASE: "团购/关系客户",
    ChannelScene.RETAIL: "门店零售",
    ChannelScene.BANQUET: "宴席/婚宴",
    ChannelScene.RESTAURANT_PAIRING: "餐饮配酒",
    ChannelScene.CORPORATE_GIFT: "企业礼品",
    ChannelScene.ONLINE_DISTRIBUTION: "线上分销/私域",
    ChannelScene.MIXED: "多种渠道",
}


class CustomerNeeds(BaseModel):
    categories: List[str] = Field(default_factory=list)
    scenes: List[str] = Field(default_factory=list)
    taste_preferences: List[str] = Field(default_factory=list)
    retail_price_min: Optional[float] = None
    retail_price_max: Optional[float] = None
    supply_price_max: Optional[float] = None
    margin_priority: Optional[str] = None
    differentiation: List[str] = Field(default_factory=list)
    brand_preference: Optional[str] = None
    order_intent: Optional[str] = None
    region_province: Optional[str] = None
    region_city: Optional[str] = None
    notes: Optional[str] = None


class CustomerProfile(BaseModel):
    customer_id: str
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    customer_type: CustomerType = CustomerType.UNKNOWN
    customer_type_confidence: float = 0.0
    channels: List[ChannelScene] = Field(default_factory=list)
    channel_mode: Optional[str] = None
    has_store: Optional[bool] = None
    store_type: Optional[StoreType] = None
    is_peer: bool = False
    needs: CustomerNeeds = Field(default_factory=CustomerNeeds)
    is_returning: bool = False
    tier: Optional[str] = None
    region: Optional[str] = None


class ProductRecommendation(BaseModel):
    sku_id: str
    name: str
    brand: str
    category: str
    supply_price: float
    suggested_retail_min: float
    suggested_retail_max: float
    margin_rate: float
    match_score: float
    match_reasons: List[str] = Field(default_factory=list)
    score_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    eligible: bool = True
    block_reason: Optional[str] = None
    differentiation_note: Optional[str] = None
    wholesale_policy: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class BusinessPlan(BaseModel):
    plan_id: str
    title: str
    pricing_strategy: str
    detailed_explanation: str = ""
    channel_fit: Optional[str] = None
    talk_tracks: List[str] = Field(default_factory=list)
    bundle_suggestions: List[str] = Field(default_factory=list)
    trial_plan: Optional[str] = None
    risk_notes: List[str] = Field(default_factory=list)


class HandoffPayload(BaseModel):
    required: bool = False
    reason: Optional[str] = None
    intent_score: int = 0
    assigned_sales_id: Optional[str] = None
    assigned_sales_name: Optional[str] = None
    callback_sla_minutes: int = 30
    conversation_summary: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QuickReply(BaseModel):
    id: str
    label: str
    value: str
    prompt: Optional[str] = None
    reply_type: str = "chip"
    style: Optional[str] = None


class CopilotResponse(BaseModel):
    session_id: str
    phase: ConversationPhase
    message: str
    quick_replies: List[QuickReply] = Field(default_factory=list)
    quick_reply_prompt: Optional[str] = None
    profile: Optional[CustomerProfile] = None
    recommendations: List[ProductRecommendation] = Field(default_factory=list)
    business_plan: Optional[BusinessPlan] = None
    business_plans: List[BusinessPlan] = Field(default_factory=list)
    handoff: Optional[HandoffPayload] = None
    actions: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationSession(BaseModel):
    session_id: str
    customer_id: str
    token: Optional[str] = None
    phase: ConversationPhase = ConversationPhase.WELCOME
    profile: CustomerProfile
    messages: List[ChatMessage] = Field(default_factory=list)
    recommendations: List[ProductRecommendation] = Field(default_factory=list)
    business_plan: Optional[BusinessPlan] = None
    business_plans: List[BusinessPlan] = Field(default_factory=list)
    handoff: HandoffPayload = Field(default_factory=HandoffPayload)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
