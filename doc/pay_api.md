# WanderMeet 微信支付（YunGouOS）— 前后端协作说明

基于 H5 / 小程序发布活动付费；**策略 A**：`POST /activities` **不校验**是否已付费（付费流程由前端保证）。

- **API 清单**：`doc/API_WanderMeet_v0.1.md` §2.4～§2.7  
- **Base URL**：`https://<域名>/api/v1/wm`

---

## 一、接口总览

| # | 方法 | 路径 | 鉴权 | 说明 |
|---|------|------|------|------|
| 1 | POST | `/pay/publish/qrcode` | Bearer | H5 扫码付，返回 `payCodeUrl` |
| 2 | POST | `/pay/state` | Bearer | 轮询是否已支付 |
| 3 | POST | `/pay/yungou/notify` | 无 | YunGouOS 异步回调 |
| 4 | POST | `/pay/publish/minipay` | Bearer | 小程序内支付（可选） |

---

## 二、公共约定

### 2.1 响应格式

成功：`{ "code": 0, "message": "ok", "data": { ... } }`  
失败：`{ "code": 40001, "message": "说明", "data": null }`（HTTP 4xx/5xx 亦可）

### 2.2 鉴权

除回调外：

```
Authorization: Bearer <accessToken>
Content-Type: application/json
```

`body.user_id` / `body.userId` 须与 token 用户一致，否则 **403**。

### 2.3 业务常量（服务端）

| 项 | 值 |
|----|-----|
| product | `publish` |
| 金额 | `1.00` 元（`PAY_PUBLISH_FEE_YUAN`） |
| 商品描述 | `发布活动` |
| 订单有效期 | 30 分钟（`PAY_ORDER_TTL_SECONDS`） |
| attach 格式 | `{userId},{qr_id},publish` |

### 2.4 环境变量（`.env`）

```env
YUNGOU_MCH_ID=
YUNGOU_API_KEY=
YUNGOU_NATIVE_API=https://api.pay.yungouos.com/api/pay/wxpay/nativePay
YUNGOU_MINAPP_API=https://api.pay.yungouos.com/api/pay/wxpay/minAppPay
YUNGOU_NOTIFY_URL=https://www.wang-hao-hao.cn/api/v1/wm/pay/yungou/notify
YUNGOU_USE_MOCK=false
PAY_PUBLISH_FEE_YUAN=1.00
PAY_PUBLISH_BODY=发布活动
PAY_PUBLISH_PRODUCT=publish
PAY_ORDER_TTL_SECONDS=1800
YUNGOU_PAY_SUCCESS_CODE=1
```

本地联调可 `YUNGOU_USE_MOCK=true`（不调 YunGouOS，返回 mock 支付链接）。

### 2.5 下单签名（与官方 Java SDK 一致）

**Native / 小程序下单**：`sign` 只对以下 **4 个必填字段** 计算，再追加 `type`、`attach`、`notify_url`、`code` 等：

`body`、`mch_id`、`out_trade_no`、`total_fee`（按 key 字典序拼接后 `&key=支付密钥`，MD5 **大写**）。

若把 `attach`、`notify_url` 等一并参与签名，YunGouOS 会返回 **「签名错误，请检查签名」**。

支付密钥路径：YunGouOS 控制台 → 微信支付 → 商户管理 → **支付密钥**（不是微信商户 API 密钥）。

---

## 三、接口 1：`POST /pay/publish/qrcode`

### 请求 Body

支持 snake_case 或 camelCase：

```json
{
  "user_id": "u_10001",
  "qr_id": "pub_1716000000_x7k2m9",
  "product": "publish"
}
```

`qr_id` 由前端生成（建议 `pub_{timestamp}_{random}`），同一用户同一 `qr_id` 支付成功后不可重复下单（409）。

### 成功 `data`

```json
{
  "qrId": "pub_1716000000_x7k2m9",
  "outTradeNo": "wm_pub_1716000123456_a1b2c3",
  "payCodeUrl": "weixin://wxpay/bizpayurl?pr=xxxx"
}
```

### 错误

| HTTP | 说明 |
|------|------|
| 400 | 缺少 qr_id |
| 403 | user_id 与 token 不一致 |
| 409 | 该 qr_id 已支付 |
| 502 | YunGouOS 调用失败 |
| 503 | 未配置 `YUNGOU_NOTIFY_URL` |

---

## 四、接口 2：`POST /pay/state`

前端约每 3 秒轮询，直到 `paid === true` 再 `POST /activities`。

### 请求 Body

```json
{
  "user_id": "u_10001",
  "qr_id": "pub_1716000000_x7k2m9",
  "product": "publish"
}
```

### 成功 `data`

已支付：

```json
{
  "paid": true,
  "state": "paid",
  "paidAt": "2026-05-18T14:30:00+08:00"
}
```

未支付 / 无单：

```json
{
  "paid": false,
  "state": "pending"
}
```

```json
{
  "paid": false,
  "state": "not_found"
}
```

`state` 还可能为：`expired`、`failed`。

---

## 五、接口 3：`POST /pay/yungou/notify`

- **无 Bearer**
- `Content-Type: application/x-www-form-urlencoded`
- 验签字段（不含 sign）：`code`, `orderNo`, `payNo`, `outTradeNo`, `money`, `mchId` → MD5 大写
- `money` 须为 `1.00`；`code` 须为 `1`（可配置）
- `attach` 第三段须为 `publish`
- 成功响应纯文本：**`SUCCESS`**；失败 **`FAIL`**

不在此接口创建活动（策略 A）。

---

## 六、接口 4：`POST /pay/publish/minipay`（可选）

### 请求 Body

```json
{
  "user_id": "u_10001",
  "qr_id": "pub_1716000000_x7k2m9",
  "product": "publish",
  "code": "wx.login 返回的 code"
}
```

### 成功 `data`

```json
{
  "qrId": "pub_1716000000_x7k2m9",
  "outTradeNo": "wm_pub_...",
  "paymentParams": {
    "timeStamp": "...",
    "nonceStr": "...",
    "package": "...",
    "signType": "RSA",
    "paySign": "..."
  }
}
```

`paymentParams` 原样传给 `uni.requestPayment`；结果仍靠 **state 轮询 + notify**。

---

## 七、不需要新增的接口

- 不单独提供「查订单列表」；前端只依赖 `state`。
- `POST /activities` **不增加**付费字段（策略 A）。
- 退款、对账走 YunGouOS 商户后台，v1 不做 API。

---

## 八、前端调用顺序

**H5**

```
登录 → POST /pay/publish/qrcode → 展示 payCodeUrl
     → 循环 POST /pay/state 直到 paid
     → POST /activities
（并行：用户付款 → YunGouOS → POST /pay/yungou/notify）
```

**小程序（预留）**

```
登录 → wx.login → POST /pay/publish/minipay → uni.requestPayment
     → POST /pay/state → POST /activities
```

---

## 九、联调检查

- [ ] `YUNGOU_NOTIFY_URL` 公网可访问  
- [ ] 付款前 `state.paid === false`  
- [ ] 付款后 notify 落库，`state.paid === true`  
- [ ] 同 `qr_id` 已付后再 qrcode → 409  
- [ ] 未登录 / 越权 `user_id` → 401 / 403  

---

## 十、数据库

表 **`wm_pay_orders`**（迁移 `20260519_0016`）：`out_trade_no` 唯一；`status`：`pending` | `paid` | `failed`。
