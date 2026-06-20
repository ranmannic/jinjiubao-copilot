# 进酒宝 AI 酒商 Copilot

登录后进酒宝 App/小程序/Web 后，通过 API 调用的 **AI 接待智能体**：识别业态 → 挖需 → 推品 → 推方案 → 转销售。

## 能力

- 客户业态分类（经销商、高端烟酒店、便利店、餐厅、会所、企业团购等）
- 渠道与需求结构化（团购/零售、品类、价格带、毛利、差异化）
- 基于进酒宝商品/价格/区域动销的 SKU 推荐
- 业务方案模板（定价、话术、试销、风险提示）
- 深水区自动转销售（议价、大批量、样品、账期等）
- **LLM 自由对话**（配置 API Key 后）：接任何话题，适时引回选品主线

## 快速启动

```bash
cd /Users/lizhengkun/Projects/jinjiubao-copilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

启动后访问：

- **聊天界面**：http://127.0.0.1:8080/
- API 文档：http://127.0.0.1:8080/docs

## Docker 部署

```bash
cp .env.example .env
docker compose up -d --build
```

## API 接口（供进酒宝系统调用）

### 1. 客户登录后创建会话

`POST /api/v1/copilot/sessions/start`

```json
{
  "customer_id": "cust_12345",
  "token": "进酒宝登录 token"
}
```

### 2. 发送消息

`POST /api/v1/copilot/chat`

```json
{
  "session_id": "sess_xxx",
  "message": "团购关系客户，想找利润型白葡萄酒",
  "quick_reply_value": "premium_wine_shop"
}
```

### 3. 查询会话状态

`GET /api/v1/copilot/sessions/{session_id}`

## 进酒宝对接接口约定

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/v1/customers/{id}` | 客户信息与等级 |
| GET | `/v1/products` | SKU、供货价、标签 |
| POST | `/v1/analytics/region-competition` | 区域竞品覆盖度 |
| POST | `/v1/crm/leads` | 创建销售线索 |
| POST | `/v1/crm/leads/assign` | 分配销售 |
| POST | `/v1/cart/items` | 加进货单 |

`APP_ENV=development` 且无 API Key 时使用内置 mock 数据。

## LLM 配置（自由对话必需）

在 `.env` 中配置（支持 OpenAI / DeepSeek / 通义等兼容接口）：

```
LLM_ENABLED=true
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

配置后 Copilot 将：
- 自然回应任意文字输入（不限快捷按钮）
- 在闲聊中适时引回选品主线
- 信息充分时自动触发推品/转销售

未配置 API Key 时降级为规则模式（仅快捷选项 + 关键词）。

```bash
pytest tests/ -q
```
