---
title: AI时代全栈知识边界·09|分层模型与HTTP
book: AI时代全栈知识边界
chapter: 网络
event: 分层模型与HTTP
sort: 1
chapter_sort: 4
created_at: 2026-06-30
source_agents: [fullstack-expert]
---
# AI时代全栈知识边界·09|分层模型与HTTP

> 前置知识:会用浏览器开发者工具看 Network 面板、能在终端敲 curl、了解进程与端口的基本概念
> 学完你能:① 把任意一次"接口慢"问题定位到 DNS/TCP/TLS/应用某一层 ② 说清 HTTPS 握手的每一步为什么存在、TLS 1.3 比 1.2 少一个 RTT 的根因 ③ 看懂 HTTP/1.1、HTTP/2、HTTP/3 的关键差异并能选型 ④ 区分 Cookie、Session、JWT 三套鉴权机制的边界 ⑤ 用 dig 追踪 DNS 迭代查询、用 curl 抓出完整的请求/响应头 ⑥ 判断哪些网络配置可交给 AI、哪些必须自己把关

### 一、概念

分层模型与 HTTP 的一句话定义:**用一组上下叠加的协议层把"比特流如何变成可用的网络服务"切成可独立演进的子问题,HTTP 是其中应用层最常用的请求/响应协议**。

先把术语对齐。OSI(Open Systems Interconnection,开放系统互连)参考模型是七层理论框架;TCP/IP(Transmission Control Protocol/Internet Protocol,传输控制协议/网际协议)是工程实际跑的四层模型;HTTP(HyperText Transfer Protocol,超文本传输协议)是应用层协议;HTTPS(HTTP Secure,安全超文本传输协议)是 HTTP over TLS,即在 TLS(Transport Layer Security,传输层安全协议)之上承载 HTTP;DNS(Domain Name System,域名系统)负责把主机名解析成 IP;CORS(Cross-Origin Resource Sharing,跨源资源共享)是浏览器同源策略的受控开口;JWT(JSON Web Token)是一种自包含的令牌格式;NAT(Network Address Translation,网络地址转换)在网关上改写 IP/端口实现内网共用公网出口。

这些概念不是孤立的,它们共同回答一个问题:**当你在浏览器敲下 URL 到看到页面,中间发生了什么、每一步可能在哪里出错**。本章不教你配 Nginx,目标是让你看懂一次完整请求在每一层的足迹,在出问题时能定位到是 DNS 没解析、TLS 没握手成功、还是应用层状态码不对。

### 二、原理

#### 1. 为什么分层:关注点分离与协议复用

分层把"网络通信"这件事切成若干垂直独立的子问题,每一层只解决一个维度。OSI 七层自下而上是物理层、数据链路层、网络层、传输层、会话层、表示层、应用层;TCP/IP 四层把前三层合并为网络接口层,会话/表示/应用合并为应用层。工程上常用五层折中模型:物理、数据链路、网络(IP)、传输(TCP/UDP)、应用(HTTP/DNS/TLS)。

分层的根本收益是**关注点分离与协议复用**。HTTP 不用关心信号是走光纤还是双绞线,因为物理层屏蔽了介质;HTTP 也不用关心丢包重传,因为 TCP 层保证可靠传输。任何一层都可以独立升级——HTTP/2 替换 HTTP/1.1 时,下层 TCP 一行代码不动;IPv6 替换 IPv4 时,上层 HTTP 同样无感知。这种"接口契约稳定、实现可替换"的分层架构,是网络能从 1980 年代演进到今天的核心原因。

数据封装(encapsulation)是分层的物理表现:应用层产出 HTTP 报文,传输层前面加 TCP 头(含源端口、目标端口、序列号),网络层前面加 IP 头(含源 IP、目标 IP、TTL),数据链路层前面加帧头(含 MAC 地址),每层只读自己的头部。排查网络问题时,沿封装层次从上往下逐层验证,就是分层模型带来的方法论。

#### 2. HTTP 三代:1.1、2、3 各自解决什么

HTTP/1.1(RFC 7230 系列,后由 RFC 9110 拆分)是文本协议,引入了 keep-alive(长连接复用 TCP)、管线化(pipelining,几乎没人用)、Host 头(支持虚拟主机)。它的核心问题是**队头阻塞(HoL,Head-of-Line Blocking)**:同一连接上,前一个响应没回来,后一个请求就得等;浏览器通常靠"同域名开 6 个并发连接"绕开,代价是握手成本翻倍。

HTTP/2(RFC 7540,后由 RFC 9113 修订)的核心改造是**二进制分帧 + 多路复用**。一个 TCP 连接里跑多个 stream(流),每个 stream 由若干 frame(帧)组成,帧可以乱序发、按 stream 重组,彻底解决了应用层的队头阻塞。配套有 HPACK 算法压缩重复的 Header、Server Push(服务端主动推资源,实测收益小,Chrome 后续移除了支持)。但 HTTP/2 仍跑在 TCP 上,**TCP 层的队头阻塞没解决**——一个包丢了,整个连接上所有 stream 都得等重传。

HTTP/3(RFC 9114)把传输层从 TCP 换成 QUIC(Quick UDP Internet Connections,RFC 9000),QUIC 跑在 UDP 上,在用户态重新实现可靠传输、拥塞控制、加密(默认集成 TLS 1.3)。关键收益:stream 之间独立,一个 stream 丢包不阻塞其他 stream;握手与加密合并,首次连接 1-RTT、复用连接可 0-RTT;连接迁移靠 Connection ID 而非"四元组(源 IP+源端口+目标 IP+目标端口)",手机从 WiFi 切 4G 不掉线。代价是 UDP 在部分企业网/防火墙被限速或阻断,部署 HTTP/3 需要确认 UDP 443 可达。

选型上:静态资源密集站点优先 HTTP/2;弱网、移动端长连接场景考虑 HTTP/3;HTTP/1.1 仅在客户端或中间代理不支持新版本时回落。

#### 3. HTTPS 握手为什么需要证书:防中间人

HTTPS 的本质是"先 TLS 握手建立加密通道,再在通道里跑 HTTP"。加密本身不难,难的是**怎么确认对端是你以为的那个人**——这就是证书(Certificate)要解决的问题。

中间人攻击(Man-in-the-Middle)的场景:你连咖啡店 WiFi,路由器把你的请求转发到自己的伪服务器,伪服务器解密后再转给真服务器。如果没有证书校验,你能"加密"通信,但加密的对象是中间人,毫无意义。

证书链解决信任问题。服务器证书由 CA(Certificate Authority,证书颁发机构)签发,CA 的根证书预置在操作系统/浏览器的信任库里。服务器在握手时发证书,客户端用预置的 CA 公钥验签——签名能验证,说明这证书确实是被信任 CA 签发的;再校验证书里的域名与实际访问域名一致、证书未过期、未吊销,才算通过。攻击者拿不到 CA 私钥就伪造不出合法证书,中间人被挡在证书校验这关。

#### 4. CORS 预检为什么存在:把决定权交给服务器

浏览器同源策略规定脚本只能访问同源(scheme + host + port 一致)的资源。CORS 是受控开口,服务器通过响应头显式授权。简单请求(GET/HEAD/POST 且 Content-Type 为表单等少数值)浏览器直接发,看响应头决定是否给脚本读;非简单请求(PUT、DELETE、自定义头、application/json)先发 OPTIONS 预检,问服务器"这种请求允许吗",允许后才发真请求。

预检的根本机制是**把"是否允许跨域"的决定权交给服务器**。HTML 表单自古能跨域发 POST,但表单的 Content-Type 与方法受限,且脚本读不到响应。当脚本想用更危险的能力(PUT、自定义头、JSON)跨域时,若直接发,服务器可能在不知情下执行了有副作用的操作。预检让浏览器先替服务器问一句"这种请求接不接受",服务器明确同意后才放行。这就是后端常收到"接口报 CORS 错"时先看 OPTIONS 通没通的原因——预检不通,真请求根本发不出去。

#### 5. Cookie/Session/JWT:状态放哪、信任凭谁

三套鉴权机制的本质差异是**状态放在哪、信任凭谁背书**。

Cookie 是浏览器持有的键值对,有域(Domain)、路径(Path)、过期(Expires/Max-Age)、Secure(仅 HTTPS)、HttpOnly(脚本不可读)、SameSite(跨站携带策略)等属性。每次请求浏览器自动带匹配的 Cookie,这是它最容易被滥用之处——CSRF(Cross-Site Request Forgery,跨站请求伪造)就是利用浏览器自动带 Cookie 这一行为发起的,SameSite=Lax/Strict 是浏览器层面的缓解,Token 放自定义头则从根本机制上规避。

Session 是服务器持有状态。服务器为每个会话生成 sessionId,通过 Cookie 下发,后续请求带 sessionId 回来,服务器根据它查自己的存储(内存/Redis)。优势是服务器可随时吊销会话(删存储即可),缺点是有状态、横向扩展要共享 Session 存储。

JWT(JSON Web Token)是无状态自包含令牌。服务器签发包含 payload 与签名的 token,客户端存(常放 localStorage 或 HttpOnly Cookie),请求时放 Authorization 头带回。服务器只验签不查存储,横向扩展天然友好。代价是**token 一旦签发,在过期前无法吊销**(除非维护黑名单,等于重新引入状态),且 payload 虽然签名防篡改但明文可读,不能放敏感信息。JWT 适合短有效期 + Refresh Token 的组合,不要把 JWT 当 Session 直接对等。

#### 6. DNS 递归与迭代:为什么分两层

DNS 解析的本质是把"www.example.com"翻译成 IP。客户端不直接问根服务器,而是问本地 DNS resolver(通常由 ISP 或公共 DNS 如 8.8.8.8 提供),resolver 替客户端跑完整条查询链,这叫递归(recursion);resolver 依次问根、顶级域、权威服务器的过程,每次拿到"下一步去问谁"的指引而不是最终答案,这叫迭代(iteration)。两者结合的根本机制是**把"慢的迭代查询"集中在 resolver 缓存,客户端只需一次轻量请求**,且 resolver 的缓存能被所有用户共享,大幅降低根与权威服务器的压力。

#### 7. NAT 与端口:为什么内网能共用一个公网 IP

端口(Port)是传输层复用的标识,16 位(0-65535),让同一台主机上的多个进程能共用一个 IP。知名端口(0-1023)留给 HTTP(80)、HTTPS(443)、DNS(53)、SSH(22)等服务;注册端口(1024-49151)和动态端口(49152-65535)给应用进程。

NAT 在网关上做"IP+端口"改写:内网主机 192.168.1.5:54321 访问外网时,网关把源地址改成公网 IP:60000,记一张映射表;响应回来时按映射表把目标地址改回 192.168.1.5:54321。这样一组公网 IP 能支撑数万条并发连接,NAT 是 IPv4 地址枯竭能拖到 IPv6 普及的关键工程手段。代价是 NAT 后的主机不能被外网主动访问(无映射条目),P2P 应用要靠 STUN/TURN 打洞。

#### 8. 负载均衡与反向代理

反向代理(Reverse Proxy)是服务器侧的代理:客户端以为自己在和源站通信,实际请求到了反向代理,代理再转发到后端。Nginx 是最常见实现。它的价值不止"分流",还包括 TLS 终止(后端跑明文 HTTP、代理处理 HTTPS,降低后端 CPU 负担)、缓存、限流、改写 URL、灰度路由。

负载均衡(Load Balancing)是反向代理的一种决策策略:把请求分发到多台后端。常见算法有轮询(round-robin)、加权轮询、最少连接(least_conn)、IP hash(同一 IP 固定打到同一台,兼容 Session 粘滞)。会话粘滞(sticky session)是 Session 时代的妥协——同一用户固定打到同一台,避免 Session 不共享;若改用 JWT 无状态,负载均衡可纯按算法分发,不需粘滞。健康检查(health check)是负载均衡的必备配套:后端某台宕机,代理要能剔除它不再分发,否则部分用户请求必然失败。

### 三、实践

#### 1. curl 抓取 HTTP 请求头与响应头

```bash
# -I 只取响应头(HEAD 请求)
curl -I https://www.example.com

# -v 显示完整交互(含请求头、响应头、TLS 握手)
curl -v https://www.example.com

# --resolve 强制把域名解析到指定 IP,绕过 DNS 排查后端
curl -v --resolve api.example.com:443:10.0.0.5 https://api.example.com/health

# 只看响应的 Server 与 Cache-Control 头
curl -sI https://www.example.com | grep -iE '^(server|cache-control):'

# 模拟跨域预检:发 OPTIONS 并带预检头
curl -i -X OPTIONS https://api.example.com/users \
  -H 'Origin: https://app.example.com' \
  -H 'Access-Control-Request-Method: PUT' \
  -H 'Access-Control-Request-Headers: Authorization,Content-Type'
```

`-v` 输出里 `>` 开头是请求行与请求头,`<` 开头是响应行与响应头,`*` 开头是 curl 自身的进度信息(含 TLS 握手细节)。预检那一条若服务器正确配置,响应应包含 `Access-Control-Allow-Origin: https://app.example.com`、`Access-Control-Allow-Methods: ..., PUT`、`Access-Control-Allow-Headers: Authorization, Content-Type`,缺任何一条浏览器都会拒绝真请求。

#### 2. HTTPS 握手流程(TLS 1.2,文字描述)

```text
客户端                                         服务器
  |                                              |
  | --- ClientHello ---------------------------> |  (1) 含 TLS 版本、客户端随机数、支持的密码套件
  |                                              |
  | <--- ServerHello --------------------------- |  (2) 选定版本、服务器随机数、选定密码套件
  | <--- Certificate --------------------------- |  (3) 服务器证书(含公钥,由 CA 签名)
  | <--- ServerKeyExchange (可选) -------------- |  (4) DH/ECDHE 参数
  | <--- ServerHelloDone ----------------------- |
  |                                              |
  | --- ClientKeyExchange ---------------------> |  (5) 客户端用服务器公钥加密的预主密钥 / ECDHE 公钥
  | --- ChangeCipherSpec ----------------------> |  (6) 通知"接下来用对称加密"
  | --- Finished ------------------------------> |  (7) 加密的握手摘要,供对方校验完整性
  |                                              |
  | <--- ChangeCipherSpec ----------------------- |
  | <--- Finished ------------------------------ |  (8) 服务器侧同样校验
  |                                              |
  | <=== 双向对称加密的应用数据 (HTTP) ========> |  (9) 之后跑 HTTP,即 HTTPS
```

整个过程 2 个 RTT(Round-Trip Time):前两个消息往返算 1-RTT,Finished 往返算第 2-RTT,加密应用数据从第 3-RTT 开始。TLS 1.3(RFC 8446)合并了 ClientHello 与 KeyExchange,把 Finished 提前,握手缩到 1-RTT;复用连接(PSK,Pre-Shared Key)可 0-RTT,首个请求随 ClientHello 一起发出,适合幂等 GET。TLS 1.3 还砍掉了所有不安全的密码套件(如 RSA 密钥交换、CBC 模式),强制前向安全(ECDHE)——即便服务器私钥未来泄漏,旧流量也无法被解密。

#### 3. DNS 解析的 dig 命令示例

```bash
# 基础查询:A 记录(IPv4 地址)
dig www.example.com A +short

# 完整响应(含查询状态、答案、权威、附加区)
dig www.example.com

# +trace 显示完整迭代查询路径:根 → 顶级域 → 权威
dig +trace www.example.com

# 查 MX 记录(邮件交换)
dig example.com MX +short

# 查 TXT 记录(常用于 SPF/DKIM/域名验证)
dig example.com TXT +short

# 指定 resolver(用公共 DNS 而非本地)
dig @8.8.8.8 www.example.com +short

# 查 CNAME 链(常见于 CDN 接入)
dig static.example.com CNAME
```

`dig +trace` 的输出能直观看到迭代查询:从根服务器(`.` 区)拿到 `.com` 顶级域服务器列表,再问 `.com` 拿到 `example.com` 的权威服务器,最后问权威服务器拿到最终 A 记录。这就是 resolver 内部每次完整解析走的路径,只是 resolver 会缓存每一步结果(TTL 决定缓存时长),用户日常请求只感受到一次本地递归。

#### 4. Nginx 反向代理 + 负载均衡最小配置

```bash
# /etc/nginx/conf.d/app.conf
upstream app_backend {
    least_conn;                       # 最少连接算法
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.2:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.3:8080 backup;      # 备用,主节点全挂才启用
}

server {
    listen 443 ssl http2;             # 启用 HTTP/2
    server_name api.example.com;

    ssl_certificate     /etc/ssl/app/fullchain.pem;
    ssl_certificate_key /etc/ssl/app/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    location / {
        proxy_pass http://app_backend;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

注意几个易错点:`proxy_set_header Host $host` 不写,后端拿到的 Host 是 `app_backend`,虚拟路由会失效;`X-Forwarded-For` 是链式追加,不能直接覆盖,否则丢失前面的代理链;若后端要拿真实客户端 IP 做风控,务必同时配置"可信代理"白名单,否则该头可被客户端伪造。HTTP/2 在 Nginx 里靠 `listen 443 ssl http2` 开启,HTTP/3 需要 `listen 443 quic reuseport` 并编译时启用 QUIC 模块,部署前确认 UDP 443 在防火墙放行。

### 四、速查/自测

#### HTTP 状态码速查表

| 类别 | 含义 | 常见码 | 说明 |
|---|---|---|---|
| 1xx | 信息性 | 100 Continue | 客户端可继续发 body |
| 2xx | 成功 | 200 OK / 201 Created / 204 No Content | 201 用于 POST 创建资源、204 用于无返回体 |
| 3xx | 重定向 | 301 永久 / 302 临时 / 304 Not Modified / 307/308 | 307/308 保持原方法,301/302 历史上会被改成 GET |
| 4xx | 客户端错 | 400 / 401 / 403 / 404 / 405 / 409 / 429 | 401 未认证、403 已认证但无权限、429 限流 |
| 5xx | 服务端错 | 500 / 502 / 503 / 504 | 502 网关收到无效响应、503 暂不可用、504 网关超时 |

#### 自测题

1. **原理层**:HTTP/2 解决了 HTTP/1.1 的队头阻塞,为什么 HTTP/3 还要换传输层?
   参考答案:HTTP/2 的多路复用只解决应用层队头阻塞,底层仍跑在 TCP 上。TCP 是字节流协议,一个包丢失会阻塞整个连接上所有 stream 的接收(哪怕其他 stream 的包已到达也要等重传),这是 TCP 层的队头阻塞。HTTP/3 换成 QUIC(基于 UDP),stream 间独立可靠传输,一个 stream 丢包不阻塞其他 stream,从根本机制上消除传输层队头阻塞。

2. **实践层**:接口偶发 502,但后端服务日志显示完全正常,你怎么定位?
   参考答案:502 是反向代理收到后端无效响应,常见原因不在业务代码而在连接层。依次排查:① 后端进程是否在监听对应端口(`ss -lntp`);② Nginx 与后端之间的 keepalive 配置,若 Nginx 复用了已被后端关闭的连接,会偶发 502;③ 后端响应时间是否超过 Nginx 的 `proxy_read_timeout`,超时也可能表现成 502/504;④ 后端是否在某段时间拒绝连接(如重启窗口)。`max_fails`/`fail_timeout` 配置不当也会让 Nginx 临时剔除健康节点。

3. **原理层**:为什么 JWT 不能放敏感信息,即使有签名?
   参考答案:JWT 由 Header、Payload、Signature 三段组成,只有 Signature 是加密计算的(Payload 是 Base64Url 编码后参与签名)。Base64Url 是可逆编码不是加密,任何人拿到 token 都能 `atob` 还原 Payload。签名只防篡改(改了 Payload 签名就对不上),不防读取。所以 JWT 不能放密码、身份证号等敏感字段,只能放 userId、角色等不敏感的标识信息。

4. **实践层**:用户反馈"网页打不开",你怀疑是 DNS 问题,如何用一条命令快速验证?
   参考答案:`dig www.example.com +short` 看是否能解析出 IP。若返回空或超时,再 `dig @8.8.8.8 www.example.com +short` 换公共 DNS 验证是否本地 resolver 故障;若仍失败,`dig +trace www.example.com` 看是哪一级断链——根、顶级域、权威哪一步拿不到下一步指引,就是问题所在。配合 `curl -v --resolve` 可绕过 DNS 直连后端,确认是否仅 DNS 层问题。

5. **原理层**:为什么 CORS 预检失败时,后端日志里看不到真请求?
   参考答案:预检是 OPTIONS 请求,浏览器只在预检通过后才发真请求(PUT/DELETE 等)。预检失败的失败信息只体现在浏览器 Console 的 CORS 错误里,后端日志只能看到 OPTIONS 请求与它返回的响应头;真请求压根没发出,自然没有日志。所以排查 CORS 问题第一步永远是看 OPTIONS 的响应头是否齐全(`Allow-Origin`、`Allow-Methods`、`Allow-Headers`、`Allow-Credentials`),而不是去找业务接口的报错。

### 可交给 AI 的部分

能放心交给 AI 的,是"模板化、可对照验收"的网络配置:Nginx 反向代理与负载均衡的完整配置块、防火墙 iptables/nftables 规则、TLS 证书申请与续期的 certbot 命令、CDN 缓存策略与回源规则、DNS 记录规划(A/CNAME/MX/TXT 该填什么)、Docker 网络与端口映射的 compose 配置。这些任务有明确的语法与对照表,AI 写错了一眼能看出来,且改起来成本可控——Nginx 配置跑 `nginx -t` 立刻知道语法对错。

不能交给 AI、必须自己把关的,是"涉及安全与隐式行为"的决策:TLS 密码套件与协议版本的取舍(关 TLS 1.0/1.1 是合规要求,AI 不一定主动禁)、CORS 的 `Allow-Origin` 是否该用 `*`(用 `*` 时不能同时 `Allow-Credentials: true`,AI 常配错)、JWT 的过期策略与 Refresh Token 设计、Session 共享存储的选型、NAT 与端口暴露的边界(把内网服务误暴露公网是常见事故)、可信代理白名单(决定 `X-Forwarded-For` 能不能信)。这些决策的特征是配错一时不报错、出事就是事故——一个 CORS 配宽了不会立即被发现,直到被攻击;一个 JWT 过期太长不会被察觉,直到 token 泄漏。

风险提示具体到三条:第一,AI 写的 Nginx 配置常漏 `proxy_set_header`,导致后端拿不到真实客户端 IP,风控与日志全错;第二,AI 写的 CORS 配置常把 `Allow-Origin: *` 配 `Allow-Credentials: true`,这是规范明确禁止的组合,浏览器会直接拒绝;第三,AI 写的 TLS 配置可能仍包含已废弃的协议(TLS 1.0/1.1)或弱密码套件(RSA 密钥交换、CBC 模式),需对照 Mozilla SSL Configuration Generator 复核。判断标准很简单:涉及"谁能访问、谁的 IP 是真的、token 多久过期、哪个端口对外"这四类安全决策时,自己过一遍原理;涉及"配置语法、记录规划、缓存策略"时,大胆交给 AI 但跑一遍校验。

## 参考来源

- [1] James F. Kurose、Keith W. Ross:《计算机网络:自顶向下方法》(Computer Networking: A Top-Down Approach)第8版 2021
- [2] Kevin R. Fall、W. Richard Stevens:《TCP/IP详解》(TCP/IP Illustrated, Volume 1)第2版 2011
- [3] RFC 9110/9112(HTTP/1.1 语义与报文):https://www.rfc-editor.org/rfc/rfc9110
- [4] RFC 9113(HTTP/2):https://www.rfc-editor.org/rfc/rfc9113
- [5] RFC 9114(HTTP/3):https://www.rfc-editor.org/rfc/rfc9114
- [6] RFC 8446(TLS 1.3):https://www.rfc-editor.org/rfc/rfc8446
- [7] RFC 9000(QUIC: A UDP-Based Multiplexed and Secure Transport):https://www.rfc-editor.org/rfc/rfc9000
- [8] MDN Web Docs《HTTP 概述》:https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Overview
- [9] Mozilla SSL Configuration Generator(参考 TLS 套件选型):https://ssl-config.mozilla.org/
- [10] 本专栏第 06 章「三件套必须掌握的内核」(同源策略与 CORS 的前端视角,本章为其网络层展开)
