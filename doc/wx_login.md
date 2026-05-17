小程序登录api
信小程序登录（替换手机号验证码）：后端改造完整方案
你现在的后端是手机号 + 验证码登录认证，要改成微信小程序一键登录，后端必须改造，但改造量很小，核心是新增一套微信登录流程，保留原有手机号登录即可兼容老用户。
我给你整理了最简可落地的改造方案，直接照着做就能上线。

---
一、核心逻辑（一句话看懂）
1. 小程序端：调用微信官方接口拿到 code → 传给后端
2. 后端：用 code 换微信 openid（用户唯一标识）
3. 后端： 
  - 有这个 openid → 直接生成 token 登录
  - 没有 → 创建新用户（绑定 openid）→ 生成 token 登录
4. 前端：拿到 token 正常请求接口（和之前手机号登录完全一致）

---
二、后端必须做的 4 个改造点
1. 数据库表修改（最小改动）
只需要给用户表加 1~2 个字段，不用删原有手机号字段：
sql
-- 用户表新增字段ALTER TABLE user ?appid=" + 小程序APPID+ "&secret=" + 小程序APPSECRET+ "&js_code=" + code
        + "&grant_type=authorization_code";// 3. 发送请求，解析返回结果WechatLoginResponse resp = httpClient.get(url, WechatLoginResponse.class);String openid = resp.getOpenid();String sessionKey = resp.getSessionKey();// 4. 数据库查询：是否已有该微信用户User user = userMapper.selectByOpenid(openid);if (user == null) {// 无用户 → 创建新用户（只存openid，手机号可以留空）
    user = new User();
    user.setOpenid(openid);
    user.setCreateTime(now());
    userMapper.insert(user);}// 5. 和原有登录一样 → 生成token返回前端String token = jwtUtil.createToken(user.getId());return Result.success(token, user);
4. 保留原有手机号登录（兼容老用户）
不用删除、不用修改原来的 /api/login/sms 接口！
- 新用户：走微信登录
- 老用户：继续用手机号验证码登录
- 后端统一用 token 鉴权，完全兼容

---
三、可选优化：微信ç¶修改，兼容运行
1 个后端开发最快 1 小时就能改完。

---
五、关键配置（提前准备）
你需要在微信公众平台拿到：
1. 小程序 AppID
2. 小程序 AppSecret（必须配置在后端，不要暴露在前端）

---
六、完整流程总结
1. 小程序获取 code → 传给后端
2. 后端用 code 换 openid
3. 查用户 → 存在则登录，不存在则创建
4. 返回统一 token → 前端正常使用
5. 原有手机号登录完全保留

---
总结
1. 后端必须改造，但改动极小
2. 核心是加字段 + 加微信登录接口
3. 原有手机号登录不用动，兼容老用户
4. 鉴权逻辑完全复用，前端只改登录页
5. 必须用：code → openid → 用户登录 这套标准流程
