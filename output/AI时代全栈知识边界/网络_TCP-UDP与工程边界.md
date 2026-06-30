---
title: AI时代全栈知识边界·10|TCP-UDP与工程边界
book: AI时代全栈知识边界
chapter: 网络
event: TCP-UDP与工程边界
sort: 2
chapter_sort: 4
created_at: 2026-06-30
source_agents:
- fullstack-expert
---
# AI时代全栈知识边界·10|TCP-UDP与工程边界

> 前置知识:理解 OSI 七层模型与 IP 层「尽力而为」(best-effort)语义
> 学完你能:① 讲清 TCP 三次握手为什么不是两次、四次挥手为什么有 TIME_WAIT ② 用 Python socket 写出可运行的 TCP 客户端/服务端 ③ 用 tcpdump 抓包并定位握手与挥手报文 ④ 在 TCP/UDP/WebSocket 间做正确选型 ⑤ 从超时/丢包/5xx/4xx 现象反向定位问题层级

### 一、概念

传输层有两大协议:TCP(Transmission Control Protocol,传输控制协议)和 UDP(User Datagram Protocol,用户数据报协议)。一句话定义:TCP 是面向连接、可靠、有序、字节流式的传输协议;UDP 是无连接、不可靠、无序、数据报式的传输协议。

两者的根本差异不在「快慢」,而在「谁来负责可靠性」。TCP 把可靠性做进协议栈内核,应用层只管读写字节流;UDP 把可靠性甩给应用层,自己只管把报文丢给 IP 层。这一差异决定了所有选型决策。

需要划清的边界:

- 「面向连接」不等于「物理连接」:TCP 的连接是两端维护的一组状态机(state machine),不是电路交换意义上的物理通路。
- 「可靠」不等于「不丢」:TCP 的可靠是「丢了就重传,最终要么送达要么通知应用层失败」,不是「永不丢失」。
- 「UDP 简单」不等于「UDP 不重要」:DNS、视频流、游戏、QUIC 都跑在 UDP 上,现代互联网流量里 UDP 占比逐年上升。

理解这一边界后,下面进入握手、挥手、拥塞控制三条主线,这是真正决定网络工程决策的内核知识。

### 二、原理

#### 1. 三次握手为什么不是两次:防历史连接

TCP 三次握手(three-way handshake)流程:

1. 客户端发 SYN(seq=x),进入 SYN_SENT 状态。
2. 服务端收到 SYN,回 SYN+ACK(seq=y, ack=x+1),进入 SYN_RCVD 状态。
3. 客户端收到 SYN+ACK,回 ACK(ack=y+1),进入 ESTABLISHED 状态。

为什么不是两次?核心原理是防历史连接(historical connection)。假设只有两次握手:客户端发了一个 SYN,因为网络拥塞滞留在路上;客户端超时后重发新 SYN,建立连接、传完数据、关闭连接。这时那个迟到的旧 SYN 到达服务端,服务端回 SYN+ACK 后立刻进入 ESTABLISHED——但客户端根本没打算连,这个连接就死在那儿,白白占用服务端资源。

三次握手能挡住这种历史连接:客户端收到服务端对旧 SYN 的 SYN+ACK 时,发现这不是自己期待的序号,回 RST 终止。三次握手的本质是「双方都要确认对方的接收能力」——只有两次时,服务端无法确认自己的 SYN 是否被客户端收到。

为什么不是四次?因为第二次握手里 SYN+ACK 合并发送,省了一个报文。三次是「最小可行」次数,四次是冗余。

#### 2. 四次挥手与 TIME_WAIT:防最后 ACK 丢失

TCP 四次挥手(four-way handshake)流程:

1. 主动方发 FIN,进入 FIN_WAIT_1。
2. 被动方回 ACK,进入 CLOSE_WAIT;此时主动方进入 FIN_WAIT_2,被动方还能发剩余数据(半关闭,half-close)。
3. 被动方发完剩余数据,发 FIN,进入 LAST_ACK。
4. 主动方回 ACK,进入 TIME_WAIT;等待 2MSL(Maximum Segment Lifetime,最大报文段寿命)后进入 CLOSED。被动方收到 ACK 后进入 CLOSED。

为什么是四次而不是三次?因为 TCP 是全双工,关闭要分两个方向各关一次。被动方收到 FIN 时可能还有数据要发,所以 ACK 和 FIN 不能合并,必须分开。

为什么主动方要 TIME_WAIT 等待 2MSL?两个原因:

- **防最后 ACK 丢失**:主动方最后的 ACK 可能丢,被动方会超时重发 FIN。如果主动方立刻 CLOSED,重发的 FIN 找不到连接,被动方永远停在 LAST_ACK。TIME_WAIT 期间还能响应重发的 FIN,重新发 ACK。
- **防历史报文**:让本次连接的延迟报文在网络中自然消亡,不被下一个复用同四元组(源 IP、源端口、目的 IP、目的端口)的连接误收。2MSL 是「报文最长寿命 × 往返」,足以覆盖任何延迟报文。

工程后果:TIME_WAIT 占用端口与内存,高并发短连接服务端会撞到 TIME_WAIT 堆积。解法是用 `SO_REUSEADDR`、长连接池、或让主动方变成服务端(让客户端先关)。不要盲目调小 `tcp_max_tw_buckets`,会破坏可靠性。

#### 3. 拥塞控制为什么需要:避免网络崩溃

TCP 拥塞控制(congestion control)解决的不是「接收方收不下」,而是「中间网络扛不住」。如果没有拥塞控制,所有连接按自己窗口猛发,路由器队列溢出、丢包、重传,进一步加剧拥塞,最终全网吞吐崩塌——这就是 1986 年互联网拥塞崩溃(congestion collapse)的根因。

四个核心算法:

- **慢启动(slow start)**:连接刚建立时 cwnd(congestion window,拥塞窗口)=1,每收到一个 ACK cwnd+1,本质是指数增长(每个 RTT 翻倍)。快速探明网络容量。
- **拥塞避免(congestion avoidance)**:cwnd 到达 ssthresh(slow start threshold,慢启动阈值)后改为线性增长,每个 RTT cwnd+1,谨慎探测。
- **快重传(fast retransmit)**:收到 3 个重复 ACK(duplicate ACK)时判定丢包,不等超时直接重传。
- **快恢复(fast recovery)**:快重传后 ssthresh = cwnd/2,cwnd = ssthresh,进入拥塞避免(不再回到慢启动)。

丢包响应分两种:超时(RTO 触发)判为严重拥塞,cwnd=1 重新慢启动;3 个重复 ACK 判为轻度拥塞,cwnd 减半。这种「重则归零、轻则减半」的策略让 TCP 在公平性与吞吐间取得平衡。

现代变体:CUBIC(Linux 默认,基于丢包)、BBR(Google 提出,基于带宽与 RTT 估计,不靠丢包判断拥塞,长肥管道性能更优)。RFC 9000 的 QUIC 用 BBR 思路在 UDP 之上重建拥塞控制。

#### 4. 滑动窗口与流量控制

滑动窗口(sliding window)解决「发送方发太快、接收方处理不过来」。接收方在 ACK 里捎带 window size(rwnd,接收窗口),告诉发送方「我还能收多少字节」。发送方在途未确认数据量不能超过 rwnd。

流量控制(flow control)是端到端的——保护接收方;拥塞控制是网络层的——保护中间链路。两者取小者作为实际发送上限:`min(cwnd, rwnd)`。

工程后果:如果接收方应用读得慢,rwnd 会缩到 0,发送方进入零窗口探测(zero window probe),定期发 1 字节探测对端窗口是否更新。这就是为什么「服务端 CPU 飙高导致业务线程读不动 socket」会表现为网络延迟飙升——根因不在网络,在应用层处理速度。

#### 5. UDP 的特性与适用场景

UDP 的特性:无连接、不保证送达、不保证顺序、报文边界保留(一次 send 对应一次 recv)。开销极低,8 字节头部(TCP 是 20 字节)。

适用场景的共同特征:**应用层自己负责可靠性,或根本不需要可靠性**。

- **DNS**:单包查询单包响应,超时重发比建连更省。
- **视频流/直播**:丢一帧不重传,重传到的也过期了,宁可丢弃。
- **多人游戏**:位置同步丢包就丢包,下一个 tick 自然覆盖。
- **QUIC**:HTTP/3 的传输层,UDP 之上重建可靠传输 + 多路复用 + 0-RTT 握手,规避 TCP 队头阻塞与内核态僵化。

选 UDP 的隐性成本:要自己实现重传、拥塞控制、序号、加密。除非走 QUIC 或有现成库,否则别轻易裸用 UDP 做「可靠传输」。

#### 6. WebSocket 与 HTTP 长连接的区别

HTTP 长连接(HTTP keep-alive):复用 TCP 连接发多个请求,但仍是请求-响应模式,服务端不能主动推送。

WebSocket:通过 HTTP Upgrade 握手升级到 WebSocket 协议(RFC 6455),握手后变全双工长连接,服务端可随时主动推送,帧开销小(2-14 字节头部)。

选型:纯请求-响应用 HTTP keep-alive;需要服务端推送(聊天、行情、协作)用 WebSocket;只需要单向推送且要兼容 HTTP 中间件用 SSE(Server-Sent Events)。

### 三、实践

#### 实验 1:Python socket 写 TCP 服务端与客户端

```python
# tcp_server.py  兼容 Python 3.10+
import socket

def run_server(host="127.0.0.1", port=9999):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(1)
        print(f"[server] listening on {host}:{port}")
        conn, addr = s.accept()
        with conn:
            print(f"[server] connected by {addr}")
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                print(f"[server] recv: {data!r}")
                conn.sendall(b"ACK:" + data)

if __name__ == "__main__":
    run_server()
```

```python
# tcp_client.py
import socket

def run_client(host="127.0.0.1", port=9999):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)  # 必须设超时,否则对端不响应会永久阻塞
        s.connect((host, port))
        s.sendall(b"hello tcp")
        reply = s.recv(1024)
        print(f"[client] reply: {reply!r}")

if __name__ == "__main__":
    run_client()
```

`SO_REUSEADDR` 让服务端重启能立刻绑定处于 TIME_WAIT 的端口,是生产环境必加项。`settimeout` 防止对端不响应永久卡死,这是新手最常漏的一行。`with` 保证 socket 异常时关闭。

#### 实验 2:tcpdump 抓包观察三次握手

```bash
# 终端1: 监听 9999 端口,打印绝对序号与时间戳
sudo tcpdump -i lo -n -tttt -S port 9999

# 终端2: 启动服务端
python tcp_server.py

# 终端3: 启动客户端
python tcp_client.py
```

预期抓到的核心报文(Flags 中 S=SYN, .=ACK, P=PUSH, F=FIN):

```
1. IP 127.0.0.1.X > 127.0.0.1.9999: S seq 0
2. IP 127.0.0.1.9999 > 127.0.0.1.X: S seq 0 ack 1
3. IP 127.0.0.1.X > 127.0.0.1.9999: . ack 1
4. IP 127.0.0.1.X > 127.0.0.1.9999: P seq 1:9 ack 1   # 数据
5. IP 127.0.0.1.9999 > 127.0.0.1.X: P seq 1:13 ack 9  # ACK:data
6-9. 四次挥手: F / . / F / .
```

关键点:`-S` 打印绝对序号(默认打印相对序号,调试时绝对更直观);`-i lo` 指定环回口,本机通信走 lo 不走 eth0;`port 9999` 是 BPF(Berkeley Packet Filter)过滤表达式,Wireshark 用显示过滤(display filter),语法不同,别混淆。

#### 实验 3:三次握手与四次挥手状态变迁(文字描述)

客户端状态变迁:

```
CLOSED --send SYN--> SYN_SENT --recv SYN+ACK, send ACK--> ESTABLISHED
                                                          |
                                            --send FIN--> FIN_WAIT_1 --recv ACK--> FIN_WAIT_2
                                                                                        |
                                                              --recv FIN, send ACK--> TIME_WAIT --2MSL--> CLOSED
```

服务端状态变迁:

```
CLOSED --listen--> LISTEN --recv SYN, send SYN+ACK--> SYN_RCVD --recv ACK--> ESTABLISHED
                                                                            |
                                                  --recv FIN, send ACK--> CLOSE_WAIT --send FIN--> LAST_ACK --recv ACK--> CLOSED
```

排查要点:

- 服务端大量 SYN_RCVD:可能是 SYN flood 攻击,或 backlog 太小,开启 `tcp_syncookies`。
- 服务端大量 CLOSE_WAIT:应用层不调 `close()`,连接泄漏,查代码里 socket 是否在异常分支漏关。
- 客户端大量 TIME_WAIT:短连接高频建连,改长连接或让对端主动关。
- 大量 FIN_WAIT_2:对端不回 FIN,应用层卡死,查对端业务逻辑。

### 四、速查/自测

#### TCP 状态变迁速查表

| 状态 | 含义 | 出现在 | 排查方向 |
|---|---|---|---|
| CLOSED | 起始/终态 | 双方 | - |
| LISTEN | 等待连接 | 服务端 | backlog 配置 |
| SYN_SENT | 已发 SYN 等回应 | 客户端 | 对端不可达/防火墙 |
| SYN_RCVD | 已发 SYN+ACK | 服务端 | SYN flood/网络抖动 |
| ESTABLISHED | 连接就绪 | 双方 | - |
| FIN_WAIT_1 | 已发 FIN | 主动方 | 等对端 ACK |
| FIN_WAIT_2 | 半关闭等对端 FIN | 主动方 | 对端应用卡死 |
| CLOSE_WAIT | 等本端 close() | 被动方 | 应用泄漏,查 close 调用 |
| LAST_ACK | 已发 FIN 等 ACK | 被动方 | ACK 丢失,等重发 |
| TIME_WAIT | 等 2MSL | 主动方 | 短连接堆积,改长连接 |
| CLOSING | 双方同时关 | 罕见 | 罕见,通常无害 |

#### 错误定位速查表

| 现象 | 可能层级 | 定位工具 |
|---|---|---|
| 连接超时(timeout) | 网络/防火墙 | ping/tcpdump/traceroute |
| Connection refused | 服务端没监听或 backlog 满 | netstat/ss/服务日志 |
| Connection reset | 中途 RST/对端崩 | tcpdump 抓 RST |
| 4xx | 客户端请求错误 | 应用日志/请求体 |
| 5xx | 服务端错误 | 应用日志/监控/火焰图 |
| 高延迟但能通 | 拥塞/CPU 飙高/零窗口 | `ss -i` 看 cwnd/rwnd,top |
| 间歇丢包 | 链路质量/MTU | mtr/`ping -s` |

#### 自测题

1. **原理层**:三次握手为什么不能是两次?请用「历史连接」场景说明。

   <details><summary>参考答案</summary>
   两次握手下,客户端一个迟到的旧 SYN 到达服务端,服务端回 SYN+ACK 后立刻 ESTABLISHED 分配资源,但客户端根本没打算连,这个连接死在服务端。三次握手下客户端收到对旧 SYN 的 SYN+ACK,发现序号不匹配,回 RST 终止历史连接。
   </details>

2. **原理层**:TIME_WAIT 为什么要等 2MSL?两个原因分别是什么?

   <details><summary>参考答案</summary>
   一是防最后 ACK 丢失:被动方超时重发 FIN 时,主动方还在 TIME_WAIT 能重新回 ACK;二是防历史报文:2MSL 足以让本次连接的延迟报文在网络中自然消亡,不被复用同四元组的下一个连接误收。
   </details>

3. **实践层**:用 tcpdump 抓本机 8080 端口的 SYN 报文,写出命令。

   <details><summary>参考答案</summary>

   ```bash
   sudo tcpdump -i lo -n "tcp[tcpflags] & tcp-syn != 0 and port 8080"
   ```
   本机走 lo,生产环境换成 eth0。`tcp[tcpflags] & tcp-syn != 0` 是 BPF 过滤 SYN 标志位。
   </details>

4. **思路层**:服务端出现大量 CLOSE_WAIT,根因在哪一层?如何定位?

   <details><summary>参考答案</summary>
   根因在应用层。CLOSE_WAIT 表示对端已 FIN 但本端没调 close()。用 `ss -ant | grep CLOSE-WAIT` 看连接,定位到对应进程,查代码里 socket/连接对象在异常分支是否漏关。常见漏点是 try/except 没在 finally 里 close,或连接池没归还。
   </details>

5. **选型层**:实时多人位置同步该用 TCP 还是 UDP?为什么?

   <details><summary>参考答案</summary>
   优先 UDP。位置数据高频发送,丢一帧下一个 tick 自然覆盖,重传反而增加延迟。若需要可靠通道(如登录、聊天)再开一条 TCP 辅助连接,或直接走 QUIC 兼顾两者。
   </details>

### 可交给 AI 的部分

可以放心交给 AI 的:

- **复杂 BPF/显示过滤表达式**:tcpdump 的 BPF 语法与 Wireshark 显示过滤语法细节繁多,AI 能根据「抓 SYN+ACK 且目标端口 443」之类的自然语言生成准确表达式。
- **抓包脚本与定时任务**:循环抓包、按大小切分、上传对象存储的 shell 脚本,AI 写得又快又准。
- **代理/负载均衡配置**:Nginx 的 upstream、健康检查、超时配置,AI 出模板后人审参数。
- **状态机图与文档**:把状态变迁画成 Mermaid/PlantUML,AI 一次性出图。
- **协议解析脚本**:用 scapy/dpkt 解析 pcap、提取握手耗时、统计重传,AI 记得 API 细节。

风险提示:

- **AI 写的网络代码常漏超时与重连**:socket 不设 timeout 会卡死,连接断开不重连会失活。这些是「必须掌握」的边界,AI 不会主动补。
- **AI 给的 tcpdump 命令常漏 -S**:默认相对序号在调试时误导,看绝对序号才准。
- **AI 不懂你的网络拓扑**:中间有 SLB/NAT/CDN 时,本地抓包看到的 RTT 与真实链路不一致,AI 给的延迟分析可能建立在错误前提上。
- **AI 倾向给「调内核参数」**:遇到 TIME_WAIT 就建议调 `tcp_tw_reuse=1`,但这个参数在 NAT 环境下会引发问题,生产环境慎用。内核参数调整必须由人把关。
- **AI 写的拥塞控制解释常停留在教科书**:真实生产里 CUBIC 与 BBR 的差异、长肥管道下的窗口缩放,AI 讲不深,需要你结合抓包与监控自己判断。

为什么这部分能交、那部分不能交:可交的部分都是「语法规则明确、出错可复现」的工具调用与配置;不能交的部分是「需要结合拓扑、内核、应用层综合判断」的诊断决策——超时定位、CLOSE_WAIT 归因、拥塞控制调参、选型权衡。AI 是高产出的初级网络工程师,你是把关的资深工程师,职责分清楚。本章讲的就是把关所需的最小内核知识。

## 参考来源

- [1] W. Richard Stevens:《TCP/IP详解 卷1:协议》机械工业出版社 2016
- [2] RFC 793:Transmission Control Protocol:https://www.rfc-editor.org/rfc/rfc793
- [3] RFC 768:User Datagram Protocol:https://www.rfc-editor.org/rfc/rfc768
- [4] RFC 9000:QUIC: A UDP-Based Multiplexed and Secure Transport:https://www.rfc-editor.org/rfc/rfc9000
- [5] RFC 6455:The WebSocket Protocol:https://www.rfc-editor.org/rfc/rfc6455
- [6] Wireshark 官方文档:https://www.wireshark.org/docs/wsug_html_chunked/
- [7] tcpdump 官方手册:https://www.tcpdump.org/manpages/tcpdump.1.html
- [8] Van Jacobson:《Congestion Avoidance and Control》SIGCOMM 1988:https://ee.lbl.gov/papers/congavoid.pdf
- [9] Linux 内核文档:TCP 协议参数:https://www.kernel.org/doc/Documentation/networking/ip-sysctl.txt
- 本专栏第 09 章「HTTP与RESTful设计」(承接传输层可靠性语义,展开应用层协议设计与 WebSocket 工程选型)
