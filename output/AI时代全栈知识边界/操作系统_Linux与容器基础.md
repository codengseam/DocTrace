---
title: AI时代全栈知识边界·12|Linux与容器基础
book: AI时代全栈知识边界
chapter: 操作系统
event: Linux与容器基础
sort: 2
chapter_sort: 5
created_at: 2026-06-30
source_agents: [fullstack-expert]
---
# AI时代全栈知识边界·12|Linux与容器基础

> 前置知识:理解进程与线程的基本区别、用过命令行、知道「文件权限」这个概念
> 学完你能:① 讲清 Linux 权限体系与软硬链接的 inode 差异 ② 用一组命令定位端口占用与资源瓶颈 ③ 区分进程五种状态与三类信号、说清容器优雅退出的根 ④ 解释容器为什么不是虚拟机、镜像分层为什么省空间 ⑤ 写出可上线的最小 Dockerfile 并识别 AI 生成容器脚本的常见漏洞

### 一、概念

Linux 与容器在全栈中的角色是「一切服务的运行底座」。一句话定义:Linux 是一类以 Linux 内核(Linux Kernel)为核心的类 Unix 开源操作系统,容器(Container)是基于该内核的 Namespace(命名空间)与 cgroups(Control Groups,控制组)两类原语实现的进程级隔离单元。

划清边界:

- 「Linux」严格说只是内核,日常说的「Linux 系统」是内核 + GNU 工具链 + 包管理器组合的发行版(如 Ubuntu、CentOS)。本文的 Linux 指「这套以 Linux 内核为核心的运行环境」。
- 「容器」不是虚拟机。虚拟机模拟完整硬件、每个实例跑独立内核;容器与宿主共享同一个内核,只是用内核原语隔离视图与限额资源。
- 「Docker」是容器的一种实现与封装,提供镜像、构建、分发工具链。容器是机制,Docker 是工具,二者不混用。

Linux 与容器的本质是同一组内核能力在不同抽象层的复用:权限、文件系统、进程、信号、Namespace、cgroups。掌握这些原语后,top 看到的数字、docker run 的隔离行为、生产事故的根因,都能在脑子里串成一条链。

### 二、原理

#### 1. 权限体系:rwx 与 inode 的耦合

Linux 文件权限的三组 rwx(读/写/执行)分别对「文件属主、属组、其他用户」三组设定。但 rwx 只是一层标记,真正的载体是 inode(Index Node,索引节点)。

inode 是文件系统里描述一个文件的元数据结构:文件类型、权限位、属主、大小、数据块位置,但不存文件名。文件名存在目录项里,目录项把文件名映射到 inode 号。理解 inode 是理解软硬链接的关键:

- 硬链接(hard link):目录项指向同一个 inode,多个文件名共享一份数据。删一个文件名只是删一个目录项,inode 的引用计数减一,归零才真正释放数据。
- 软链接(symbolic link,符号链接):一个独立文件,内容是另一个文件的路径字符串。它有自己的 inode,目标文件被删后软链接变成悬空链接。

这条差异决定了它们的使用边界:硬链接不能跨文件系统(inode 编号空间不通用)、不能链接目录(避免循环引用);软链接可以跨文件系统、可以链接目录,但依赖目标路径存在。

权限之外还有 sudo(substitute user do):允许普通用户以 root 身份执行特定命令。sudo 的安全模型是「白名单 + 密码 + 审计」,配置在 /etc/sudoers。生产环境的一个常见漏洞是给某账号 `NOPASSWD: ALL`,等于把 root 权限裸奔给该账号——这是容器镜像与 CI 流水线里反复出现的隐患。

#### 2. 进程状态与信号:容器优雅退出的根

Linux 进程有五种核心状态,记住缩写就能读懂 top 与 ps 的输出:

- R(Running/Ready,运行/就绪):正在 CPU 上跑或等待 CPU。
- S(Sleeping,可中断睡眠):等待事件(如 IO 完成、信号),可被信号唤醒。
- D(Uninterruptible Sleep,不可中断睡眠):通常在等磁盘 IO,不响应信号,kill 不掉。
- Z(Zombie,僵尸):进程已退出但父进程尚未回收它的退出状态,残留 PCB(Process Control Block,进程控制块)。
- T(Stopped,停止):被 SIGSTOP 暂停或被调试器挂起。

信号(Signal)是 Unix 系统里进程间异步通知的机制。容器与服务的「优雅退出」全靠它。三类信号最常用:

- SIGTERM(termination signal,终止信号,信号 15):请求进程自行退出,进程可捕获后做清理(关闭连接、flush 日志、停止接收新请求)。这是 `docker stop` 与 `kill <pid>` 默认发送的信号。
- SIGKILL(kill signal,强制杀死信号,信号 9):内核直接终结进程,不可捕获、不可忽略。`kill -9` 与 `docker kill` 发的是它。代价是资源可能泄漏(临时文件、未 flush 的缓冲)。
- SIGHUP(hangup signal,挂起信号,信号 1):原意是终端断开,现常被守护进程(daemon)重载为「重新读取配置」。

为什么这条对容器至关重要:Dockerfile 的 `ENTRYPOINT` 或 `CMD` 决定了容器内 PID 1 进程是谁。如果 PID 1 是个 shell 包装脚本而不转发信号,`docker stop` 时 SIGTERM 发给 shell,shell 不传给真正的业务进程,业务进程收不到信号,Docker 等待 10 秒超时后发 SIGKILL 强杀——服务就被「硬拔电源」式退出,正在处理的请求中断、缓冲丢失。这就是「容器必须用 exec 形式的 ENTRYPOINT 或用 tini 做 init 进程」的根本机制。

#### 3. 资源瓶颈判断:load average 与「CPU 高 IO 低」

线上排查的第一步永远是判断「瓶颈在哪」。load average(平均负载)是入门指标,它反映「系统在过去 1/5/15 分钟内,平均有多少进程处于 R 或 D 状态」。注意它把「等 CPU」和「等磁盘 IO」混在一起算——load 高不一定是 CPU 不够,也可能是磁盘卡。

判断口诀:

- CPU% 高、IO 低 → CPU 瓶颈,优化算法或加核。
- CPU% 低、IO 高(iowait 高) → 磁盘瓶颈,常见于数据库、日志服务。
- load 高但 CPU% 都低 → 多数进程在等 IO(D 状态),典型磁盘瓶颈。
- 内存高、swap 在动 → 内存瓶颈,可能触发 OOM Killer(内核的内存回收与杀进程机制)。

这套判断的根在两条命令:`top`/`htop` 看 CPU 与内存概览、进程级占用;`iostat`/`vmstat` 看磁盘与系统级 IO。`free -h` 看 memory 与 buffer/cache;`df -h` 看文件系统已用空间;`du -sh` 看目录占用。它们的分工:`free` 是「内存水位」、`df` 是「磁盘容量」、`du` 是「谁占了空间」、`iostat` 是「磁盘是否在排队」。

#### 4. 容器不是虚拟机:共享内核与 Namespace/cgroups

虚拟机(Virtual Machine,VM)的本质是硬件虚拟化——Hypervisor 模拟 CPU、内存、网卡,每个 VM 跑一个完整内核。隔离强但代价大:每个 VM 要装整套操作系统,GB 级镜像,秒级启动。

容器走另一条路:不虚拟硬件,直接复用宿主内核,只隔离「进程看到的视图」与「能用的资源」。隔离视图靠 Namespace,限制资源靠 cgroups。二者都是 Linux 内核早已存在的能力,容器只是把它们组合封装成易用工具。

Namespace 的六种类型,各自隔离一类视图:

- PID:容器内进程看不到宿主进程,自己从 PID 1 开始编号。
- NET:独立网卡、IP、路由表、端口空间。
- MNT:独立文件系统挂载视图。
- UTS:独立 hostname 与 domainname。
- IPC:独立消息队列、共享内存。
- USER:容器内 root 映射到宿主非 root,提升安全性。

cgroups 则负责资源限额,常见三类:CPU(限制 CPU 时间片或配额)、MEM(限制内存上限,超限触发 OOM)、BLKIO(限制块设备 IO 带宽)。Namespace 管「看到什么」,cgroups 管「能用多少」,合起来才是完整的容器。

#### 5. 镜像分层与 Copy-on-Write:为什么省空间

Docker 镜像不是单个文件,而是一组只读层(layer)的叠加。每条 Dockerfile 指令(FROM、RUN、COPY 等)产生一层。容器启动时,在镜像层之上叠加一个可写层(container layer)。

这套机制依赖 UnionFS(Union File System,联合文件系统),它把多个目录「联合挂载」成一个目录树。读文件时从上往下找,先匹配先用;写文件时触发 Copy-on-Write(写时复制):要修改某层文件,先把文件从下层复制到可写层,再修改副本,下层只读层不动。

省空间的根因有两层:

- 同一基础镜像被多个镜像复用时,宿主只存一份(共享只读层)。
- 同一镜像被多个容器实例使用时,只读层共享,每个容器只额外占一份薄可写层。

代价是写性能略低(第一次写要先复制),但读性能与裸盘接近。这就是为什么「一个 ubuntu 基础镜像 + 几百个业务镜像」只占少量磁盘,而「几百个 VM 镜像」要占几百 GB。

### 三、实践

#### 实践 1:找出占用 8080 端口的进程

线上最常见的排查场景:启动服务报「端口被占用」。下面这组命令层层递进,可定位到具体进程并清理。

```bash
# 第 1 步:看 8080 端口被谁监听(推荐 ss,比 netstat 快)
ss -ltnp | grep :8080
# 输出示例: LISTEN 0 128 *:8080 *:* users:(("python",pid=12345,fd=3))

# 第 2 步:netstat 兼容老系统(无 ss 时)
netstat -ltnp | grep :8080

# 第 3 步:用 lsof 反查(已知端口找进程,一步到位)
lsof -i :8080
# 输出示例: COMMAND  PID    USER   FD  TYPE  DEVICE  SIZE/OFF NODE NAME
#          python  12345 appuser   3u  IPv4 1234567       0t0  TCP *:8080 (LISTEN)

# 第 4 步:已知 PID 反查进程详情与工作目录
ps -fp 12345
ls -l /proc/12345/cwd                       # 看进程工作目录
cat /proc/12345/cmdline | tr '\0' ' '       # 看完整启动命令

# 第 5 步:确认后优雅退出(先 SIGTERM)
kill 12345
# 10 秒后仍未退出再强杀(SIGKILL,不可捕获)
kill -9 12345
```

关键点:`ss` 与 `netstat` 的 `-p` 参数需要 root 权限才能看到进程名;`lsof -i :8080` 一步到位,是排查端口占用的最短路径。`/proc/<pid>/` 是 Linux 内核暴露的进程信息伪文件系统,`cwd`、`exe`、`cmdline` 三个文件分别对应工作目录、可执行文件、启动命令,排查「这个进程到底跑的是什么」时比 ps 更可靠。

#### 实践 2:一个最小可上线的 Dockerfile

下面这个 Dockerfile 给一个 Python FastAPI 服务,涵盖多阶段构建、非 root 用户、exec 形式 ENTRYPOINT 三条生产规范。

```dockerfile
# ---- 构建阶段 ----
FROM python:3.12-slim AS builder
WORKDIR /app
# 先拷依赖文件,利用层缓存:依赖不变则跳过 pip install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- 运行阶段 ----
FROM python:3.12-slim
WORKDIR /app
# 拷依赖
COPY --from=builder /install /usr/local
# 拷代码
COPY app.py .
# 创建非 root 用户并切换
RUN useradd -r -u 1000 appuser && chown -R appuser /app
USER appuser
# exec 形式:确保 python 是 PID 1,直接接收 SIGTERM
ENTRYPOINT ["python", "app.py"]
```

三条规范的原因:多阶段构建把编译期依赖留在 builder 层,运行镜像只含运行所需,镜像从 GB 级降到百 MB 级;非 root 用户防止容器逃逸后直接拿到宿主 root;`ENTRYPOINT` 用 JSON 数组(exec 形式)而不是字符串(shell 形式),关键差异是 shell 形式下真正的进程是 `/bin/sh -c "python app.py"`,sh 不会转发信号给 python,`docker stop` 会变成硬杀——这正是上一节讲的优雅退出根因。

#### 实践 3:docker run 时 Namespace 隔离的演示

下面这组命令直观展示容器内外的视图差异,可在任意装了 Docker 的 Linux 上复现。

```bash
# 宿主端:看自己的 PID 与 hostname
echo $$                       # 假设输出 5000,宿主 shell 的 PID
hostname                      # 假设输出 prod-host-01
ip addr                       # 看宿主网卡 eth0 等

# 启动一个容器,用 alpine 跑 shell
docker run -it --rm --name ns-demo alpine sh

# 容器内:同样的命令,结果完全不同
echo $$                       # 输出 1,容器内进程是 PID 1
hostname                      # 输出一串随机哈希(独立 UTS Namespace)
ip addr                       # 只有 lo 与 eth0,IP 是 172.17.x.x(独立 NET Namespace)
ps aux                        # 只能看到容器内进程,看不到宿主几千个进程(独立 PID Namespace)

# 退出容器后,在宿主用 lsns 看所有 Namespace
lsns                          # 列出当前系统所有 Namespace 及其进程

# 用 nsenter 进入某容器的 Namespace 调试(排查网络问题时常用)
docker inspect --format '{{.State.Pid}}' ns-demo   # 拿到容器主进程在宿主的 PID
# 假设输出 23456
nsenter -t 23456 -n ip addr   # 进入它的网络 Namespace 看 IP
nsenter -t 23456 -m ls /      # 进入它的挂载 Namespace 看根目录
```

关键点:容器内看到的「PID 1」「独立 hostname」「独立网卡」全部是 Namespace 制造的视图隔离,进程在宿主内核里仍然是一个普通进程,有自己的真实 PID(可通过 `docker inspect` 拿到)。`nsenter` 是排查容器网络与文件系统问题时的「后门」——容器内工具不全时,用宿主的工具进入它的 Namespace 操作。这条也是理解「容器不是虚拟机」最直观的方式:VM 里看到的就是 VM 自己的内核,容器里看到的是宿主内核的一个过滤视图。

### 四、速查/自测

#### Linux 排查命令速查表

| 排查目标 | 首选命令 | 备选/补充 | 关键参数或要点 |
|---|---|---|---|
| 端口被谁占用 | `lsof -i :PORT` | `ss -ltnp` / `netstat -ltnp` | `-p` 需 root 看进程名 |
| 进程详情 | `ps -fp PID` | `top -p PID` | `/proc/PID/cmdline` 更全 |
| CPU/内存概览 | `top` / `htop` | `vmstat 1` | load average 看第一行 |
| 磁盘容量 | `df -h` | `df -i` 看 inode 是否用尽 | - |
| 目录占用 | `du -sh *` | `du -h --max-depth=1` | 排查大目录 |
| 磁盘 IO 压力 | `iostat -x 1` | `iotop` | `%util` 高即瓶颈 |
| 系统级 IO/上下文切换 | `vmstat 1` | `sar` | `b` 列高即 D 状态多 |
| 内存水位 | `free -h` | `cat /proc/meminfo` | 看 available 而非 free |
| 网络连接 | `ss -tnp` | `netstat -tnp` | `ESTAB` 数看长连接 |
| 进程打开的文件 | `lsof -p PID` | `ls /proc/PID/fd` | 排查 too many open files |
| 软链接指向 | `readlink -f file` | `ls -l` | 硬链接用 `ls -i` 看 inode |
| 优雅停止进程 | `kill PID` | `kill -9 PID`(强杀) | 先 TERM 后 KILL |

#### 自测题

1. **原理层**:硬链接与软链接的本质区别是什么?为什么硬链接不能跨文件系统?

   <details><summary>参考答案</summary>
   硬链接是多个目录项指向同一个 inode,共享同一份数据;软链接是独立文件,内容是目标路径字符串,有自己的 inode。硬链接不能跨文件系统,因为不同文件系统的 inode 编号空间独立,跨系统无法用 inode 号定位数据;也不能链接目录,因为会引入循环引用风险。软链接存的是路径字符串,可跨任意挂载点。
   </details>

2. **思路层**:服务报 `port 8080 already in use`,但普通用户 `ps` 找不到对应进程,可能是什么原因?怎么继续排查?

   <details><summary>参考答案</summary>
   常见原因:进程以非当前用户身份运行(普通 ps 看不到别人的完整信息)、是容器内进程(宿主 ps 不直接显示)、或处于 D/Z 状态。排查路径:用 `sudo ss -ltnp | grep :8080` 或 `sudo lsof -i :8080`(加 root 权限看进程名),拿到 PID 后 `ps -fp PID`、`ls -l /proc/PID/exe` 看可执行文件;如果是容器,用 `docker ps` 看哪个容器映射了 8080。
   </details>

3. **实践层**:`docker stop` 后服务日志显示「进程被 KILL 强杀」,但代码里明明写了 SIGTERM 处理逻辑。最可能的原因是什么?怎么修?

   <details><summary>参考答案</summary>
   最可能是 Dockerfile 的 `ENTRYPOINT` 用了 shell 形式(`ENTRYPOINT python app.py`),导致 PID 1 是 `/bin/sh -c` 而不是业务进程,sh 不转发 SIGTERM 给 python,10 秒后 Docker 发 SIGKILL。修复:改成 exec 形式 `ENTRYPOINT ["python", "app.py"]`,或用 tini 做 init 进程;如果信号被 bash 启动脚本吞掉,在脚本里用 `exec python app.py` 让 python 替换 bash 成为 PID 1。
   </details>

4. **原理层**:容器为什么比虚拟机轻量?「共享内核」带来什么安全风险?

   <details><summary>参考答案</summary>
   容器与宿主共享内核,不虚拟硬件、不跑独立内核,镜像只含应用与运行时依赖,启动是进程级开销(毫秒到秒)。代价是隔离强度弱于 VM:内核漏洞(如 Dirty COW)可被容器内进程利用逃逸到宿主;不同容器共享同一内核,一个容器触发内核 panic 会拖垮整个宿主。高隔离场景(多租户、不可信代码)仍需 VM 或 Kata Containers 这类「VM 级隔离的容器」。
   </details>

5. **思路层**:load average 是 8,但 `top` 里所有进程 CPU% 加起来不到 100%(机器 4 核),瓶颈在哪?下一步看哪个命令?

   <details><summary>参考答案</summary>
   load average 把 R(等 CPU)与 D(等 IO)状态都算进去,CPU% 低而 load 高,说明多数进程在 D 状态等磁盘 IO,瓶颈在磁盘而非 CPU。下一步看 `iostat -x 1`,关注 `%util`(接近 100% 表示磁盘饱和)、`await`(高表示 IO 响应慢)、`r/s w/s`(读写 IOPS);再看 `vmstat 1` 的 `b` 列(D 状态进程数),`b` 持续高即磁盘瓶颈确认。
   </details>

### 可交给 AI 的部分

可以放心交给 AI 的:

- **完整 Shell 脚本**:批量清理日志、定时备份、日志分析聚合这类「目标明确、可观测」的脚本,AI 写得比手敲快。给出输入输出格式与边界条件即可。
- **Dockerfile 编写**:已知基础镜像与依赖列表,AI 能生成多阶段构建、非 root 用户、exec 形式 ENTRYPOINT 的完整 Dockerfile。
- **Docker Compose 编排**:多服务依赖、网络、卷挂载的 compose.yaml 初版,AI 出模板后由人审。
- **排查命令组合**:把症状描述清楚,AI 能给出 ss/lsof/iostat 的命令组合与解读思路,适合做「现场速查」。
- **Bash 管道 one-liner**:统计日志 UV、提取某字段并排序去重这类管道组合,AI 比人记得全。

风险提示:

- **AI 写的 Shell 经常漏 `set -euo pipefail`**:没有 `set -e`,中间命令失败脚本继续跑,可能误删数据;没有 `set -u`,变量名打错变成空字符串;没有 `pipefail`,管道中间失败被吞。这三项必须由人补上。
- **AI 写的 Dockerfile 容易漏 `.dockerignore`**:把 `.git`、`node_modules`、`__pycache__` 拷进镜像,镜像膨胀且可能泄露密钥。`.dockerignore` 必须由人配置。
- **AI 默认用 root 跑容器**:生成的 Dockerfile 经常不创建非 root 用户,直接以 root 运行,容器逃逸风险高。生产规范必须由人强制。
- **AI 不懂层缓存优化**:经常把 `COPY . .` 放在 `RUN pip install` 之前,导致每次代码变更都重装依赖,构建慢十倍。指令顺序必须由人审。
- **AI 写的信号处理经常错**:Python 的 `signal.signal` 在多线程下只在主线程生效,asyncio 还要用 `loop.add_signal_handler`,AI 经常给出跑不通的样板。优雅退出逻辑必须实测。
- **AI 对资源限额的判断不可靠**:让它「限制容器 2 核 4G」,AI 会写 `--cpus=2 --memory=4g`,但不会提醒 Java/Python 的 GC 与 OOM 行为在 cgroups 限制下可能反常(JVM 看不到容器内存上限会按宿主内存设堆,导致被 OOM Killer 反复杀)。这种边界必须人把关。

为什么这部分能交、那部分不能交:可交的都是「结构化、可观测、可回滚」的产出——脚本跑错能看日志、Dockerfile 构建失败能重跑。不能交的是「需要内核知识才能判断」的决策:信号转发路径、层缓存顺序、容器内存与运行时 GC 的交互、安全边界。这些一旦错,出的是线上事故而非构建报错。AI 是高产出但无安全意识的执行者,你是把关者,本章讲的就是把关所需的最小内核知识——数据库一章会反复用到资源瓶颈判断与容器隔离这两条视角。

## 参考来源

- [1] Robert Love:《Linux 内核设计与实现》机械工业出版社 2011
- [2] Daniel J. Barrett:《Linux 命令速查手册》人民邮电出版社 2019
- [3] Linux man pages:https://man7.org/linux/man-pages/
- [4] kernel.org cgroups v2 文档:https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html
- [5] namespaces(7) man page:https://man7.org/linux/man-pages/man7/namespaces.7.html
- [6] Docker 官方文档:Dockerfile reference:https://docs.docker.com/engine/reference/builder/
- [7] Docker 官方文档:OverlayFS 联合文件系统驱动:https://docs.docker.com/storage/storagedriver/overlayfs-driver/
- [8] Jeff Anderson:《Docker 实战》人民邮电出版社 2019
- [9] signal(7) man page:https://man7.org/linux/man-pages/man7/signal.7.html
- 本专栏第 11 章「进程线程与内存」(本章的进程状态、信号机制、内存水位判断直接延续其进程与内存模型)
