---
title: AI时代全栈知识边界·08|可交给AI的部分
book: AI时代全栈知识边界
chapter: 前端
event: 可交给AI的部分
sort: 3
chapter_sort: 3
created_at: 2026-06-30
source_agents:
- fullstack-expert
---
# AI时代全栈知识边界·08|可交给AI的部分

> 前置知识:读过三件套必须掌握的内核一篇,知道闭包、this、事件循环、盒模型、层叠上下文、重排重绘属于必须自己把关的内核,不会随 AI 进化而退场
> 学完你能:① 用一句话定义前端"可交给 AI 的部分"并说出判据 ② 把第 02 篇三条判据(识错/选型/定位)反推到前端可交工作上,验证某项任务能否放手 ③ 让 AI 写响应式卡片并写出测试用例暴露其移动端断点缺陷 ④ 让 AI 写表单校验正则,补上空值、Unicode、超长三类边界 ⑤ 让 AI 写 CSS 动画并核对 transform 与 opacity 的性能正确性 ⑥ 识别 AI 前端产出的四类风险(浏览器兼容、原型链、表单边界、SVG 可访问性)

## 一、概念

### 1. 一句话定义

前端"可交给 AI 的部分",是那些出错会立即在视觉层显形、不依赖隐性业务上下文、修复成本可控的实现层工作。它包括精美页面样式、复杂动画代码(transition / animation / keyframes)、适配多端的 CSS(Responsive Web Design,响应式网页设计、Media Query,媒体查询)、基于 Tailwind / Ant Design / Element 的完整页面模板、表单校验正则、UI 组件完整封装、Autoprefixer(自动前缀工具)生成的兼容性前缀、Sass / Less 这类 Preprocessor(CSS 预处理器)的完整代码。

这条定义的边界刻得很细:"实现层"才交,"原理层"不交。CSS 选择器写法可交,层叠上下文为什么压不住子元素的 z-index 不交;transition 的语法可交,为什么动画要避开 left 走 transform 不交;媒体查询断点可交,断点背后"移动端 WebView 兼容"这层隐性约束不交。分界线和第 06 篇里"必须掌握的内核"恰好互补:那边讲的是浏览器内部不可委托的规则集,这边讲的是规则集之上、错误可见的样板层。

### 2. 与三件套内核的边界关系

三件套内核解决"为什么这样写能 work、那样写会出 bug",可交给 AI 的部分解决"长什么样、什么动画、什么布局"。两边的分野由"错误可见性"决定:内核层的 bug 是隐性的(闭包泄漏要等组件卸载后才爆、z-index 失效只在特定滚动位置才出现),AI 写出来你一眼看不出对错;可交层的 bug 是显性的(卡片在 320px 下溢出、动画卡顿、断点没生效),浏览器一开就知道。错误是否隐性,是判断前端工作能否交给 AI 的唯一硬指标。

### 3. 几个术语的中英对照

下面这些词会反复出现,先给对照:Responsive Web Design(响应式网页设计)、Media Query(媒体查询)、Breakpoint(断点)、Autoprefixer(自动前缀工具)、Preprocessor(CSS 预处理器)、Accessibility(无障碍,缩写 a11y)、Viewport(视口)、Caniuse(浏览器兼容性查询表,caniuse.com)、DocumentFragment(文档片段)。

## 二、原理

### 1. 三条判据的反推:为什么这部分能交

第 02 篇给出三条判据(识错 / 选型 / 定位),任一条答"不能"即归入必须掌握。三条判据是 OR 关系,反过来用就是"可交"的判定式:三条全答"能",才能放手。前端可交的工作,恰好在这三条上都答"能"。

判据一·错误识别:可交工作的错误是显性的。响应式卡片在 320px 下溢出,DevTools 切一下设备就看见;动画用了 left 触发重排,帧率立刻掉;媒体查询断点没生效,窗口拖一下就发现。识错成本接近零,不需要你心里先有"正确答案的样子",浏览器替你做了比对。

判据二·选型判断:可交工作的选型不依赖隐性业务上下文。响应式断点 768px / 1024px 是行业惯例,不是业务约束;Tailwind 还是 Ant Design 由团队技术栈定,不是 AI 替你猜;flex 一维还是 grid 二维由布局维度决定,不依赖订单量或并发数。AI 不需要拿到"用户行为日志"才能给你写卡片,而 SQL 索引设计、Redis 还是 Memcached 这种判据二的典型场景,不拿到业务约束 AI 是答不出来的。这条对照把"可交"和"不可交"的本质划清。

判据三·问题定位:可交工作的故障有明确报错。CSS 语法错了控制台红字、媒体查询不匹配样式不生效、动画属性写错不播放,定位路径直接。不像闭包泄漏要追引用链、不像 z-index 失效要爬 DOM 树找层叠上下文、不像跨域 OPTIONS 没通要查后端中间件——那些才是判据三的硬骨头,必须自己掌握。

### 2. 错误可见性的根本机制

错误之所以"可见",根子在 CSS / HTML 的声明式本性。声明式语言的特性是"结果由描述决定,不由执行路径决定":你写 `display:flex` 浏览器就给你 flex 布局,写错了立刻不 flex;你写 `@media (max-width:768px)` 浏览器就只在视口 ≤ 768px 应用规则,断点不对立刻不生效。没有"先跑一段、再跑一段、中间持有引用、十秒后才体现"的执行路径,也就没有隐式失效的空间。

JavaScript 的行为层之所以不能全交,正因为它是命令式的:执行有时序、引用有持有者、回调有排队顺序。AI 写一段 `setInterval` 闭包持有大数组,语法全对、运行也对、十分钟后内存涨上去——这种隐性失效是命令式语言的天然属性。CSS 动画虽然也"跑起来",但它的状态由关键帧描述、由浏览器合成,不存在"用户卸载组件后回调还在跑"的悬挂路径。这就是为什么同样是"动画",CSS keyframes 可交、JavaScript 的 requestAnimationFrame 闭包要审。

### 3. 边界会移动:工具进化让更多 CSS 可交

第 02 篇讲过边界随工具移动。前端可交一侧的边界近年在快速外扩:Tailwind 把无数媒体查询封装进 `sm:` `md:` `lg:` 前缀,AI 写一行 `md:grid-cols-3` 就完成了过去要手写整套断点的活;Autoprefixer 让 AI 不必关心 `-webkit-` `-moz-` 前缀;CSS Houdini 的 Worklet 让一部分过去要 JavaScript 才能做的特效落到 CSS 层。工具每升级一档,可交一侧就扩一段。但扩的不是"原理",是"写法"——`md:grid-cols-3` 背后的"为什么 768px 是断点"仍要懂,否则 AI 给你 `sm:grid-cols-4` 你看不出断点选错了。

## 三、实践

### 1. 让 AI 写响应式卡片,用测试用例暴露断点缺陷

这是本章核心案例。给 AI 的提示词大致是"写一个响应式卡片,桌面三列、平板两列、手机一列,带图片、标题、简介、按钮"。AI 交回来的初版往往是这样的:

```html
<div class="card-grid">
  <article class="card">
    <img src="cover.jpg" alt="封面">
    <div class="card-body">
      <h3 class="card-title">卡片标题</h3>
      <p class="card-desc">这是一段简介,展示卡片可承载的文本内容长度。</p>
      <button class="card-btn">查看详情</button>
    </div>
  </article>
  <!-- 更多卡片 -->
</div>
```

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  padding: 24px;
}
@media (max-width: 768px) {
  .card-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .card-grid { grid-template-columns: 1fr; }
}
.card-title { font-size: 18px; font-weight: 600; }
.card-desc { font-size: 14px; color: #666; }
.card-btn { padding: 8px 16px; font-size: 14px; }
```

表面上挑不出毛病:三档断点齐全、grid 用得规范、字号合理。把这份代码塞进真实测试用例,缺陷就暴露了。

测试用例(直接可跑的验收脚本):

```javascript
// tests/test_responsive_card.js
// 用 Playwright 跑断点回归,暴露 AI 初版的移动端缺陷
const { test, expect } = require('@playwright/test');

const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'tablet',  width: 768,  height: 1024 },
  { name: 'mobile',  width: 375,  height: 667  },
  { name: 'se',      width: 320,  height: 568  }, // iPhone SE 极小屏
];

for (const vp of VIEWPORTS) {
  test(`卡片在 ${vp.name}(${vp.width}px) 下不溢出`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('http://localhost:8080/card.html');
    const grid = await page.locator('.card-grid');
    const box = await grid.boundingBox();
    // 断言一:grid 宽度不超过视口
    expect(box.x + box.width).toBeLessThanOrEqual(vp.width);

    // 断言二:每个卡片按钮的触摸目标 ≥ 44px(iOS HIG 推荐)
    const btn = page.locator('.card-btn').first();
    const btnBox = await btn.boundingBox();
    expect(Math.min(btnBox.height, btnBox.width)).toBeGreaterThanOrEqual(44);

    // 断言三:极小屏下卡片不应并列
    if (vp.width <= 480) {
      const cols = await grid.evaluate(el =>
        getComputedStyle(el).gridTemplateColumns.split(' ').length
      );
      expect(cols).toBe(1);
    }
  });
}
```

跑一遍,在 320px 的 SE 视口下,断言一很可能挂:`grid.x + grid.width > 320`。原因是 AI 漏了 `box-sizing:border-box` 之外的几条:`padding:24px` 让 grid 的内容区在 320px 视口下只剩 272px,但 grid-template-columns 的 `1fr` 加上默认 `min-width:auto`,当卡片内的长单词或图片不收缩时,grid 会撑爆容器。AI 没写 `minmax(0, 1fr)`,也没给 `.card img` 写 `max-width:100%; height:auto`。

把缺陷写回给 AI,让它修,第二轮它会补上:

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
  padding: 24px;
  box-sizing: border-box;
  max-width: 100%;
}
.card img {
  max-width: 100%;
  height: auto;
  display: block;
}
* { box-sizing: border-box; }
```

这一轮跑测试,断言一通过。但断言二在 320px 下仍可能挂:按钮高度只有 32px,因为 `padding:8px 16px` 加 `font-size:14px` 算出来 30px 出头,达不到 iOS HIG 推荐的 44px 触摸目标。这是 AI 写卡片时最常漏的——它默认桌面审美,不会主动想到拇指点击的物理尺寸。第三轮把 `padding` 提到 `12px 20px`、`min-height:44px`,全部断言通过。

这个案例的三轮迭代演示了"可交"的真实形态:写法层确实可交,AI 三轮内能给出正确代码;但每轮的"错在哪、怎么验"必须由人主导。AI 不会主动写 `minmax(0, 1fr)`,因为它不知道你的卡片内容会不会撑爆;AI 不会主动设 `min-height:44px`,因为它没把触摸目标当约束。识错(用 Playwright 暴露溢出)、选型(决定断点取 320/480/768)、定位(看到溢出后定位到 min-width:auto)——三条判据在每一轮里都被你调用,AI 只负责填代码。

### 2. 让 AI 写表单校验,补三类边界

表单校验正则是 AI 最拿手的活之一,但也最容易在边界上漏。给 AI 的需求是"写一个用户名校号校验:4-20 位,字母数字下划线"。AI 交回来:

```javascript
function validateUsername(name) {
  return /^[a-zA-Z0-9_]{4,20}$/.test(name);
}
```

看起来对。把三类边界喂进去:

```javascript
const cases = [
  { input: 'alice_01',    expect: true  }, // 正常
  { input: 'ali',          expect: false }, // 太短
  { input: 'a'.repeat(21), expect: false }, // 超长
  { input: '',             expect: false }, // 空值
  { input: '   ',          expect: false }, // 全空格
  { input: '  alice  ',    expect: false }, // 带空格
  { input: 'alice\u00a0',  expect: false }, // 末尾带 NBSP
  { input: 'café',         expect: false }, // Unicode 字母
  { input: '小明',          expect: false }, // 中文
  { input: 'a'.repeat(20), expect: true  }, // 正好 20 位
];
for (const c of cases) {
  if (validateUsername(c.input) !== c.expect) {
    console.error('FAIL', JSON.stringify(c.input), c.expect);
  }
}
```

跑一遍,AI 的初版会在三个用例上挂:空字符串 `''` 返回 false(凑巧对,但若把 `{4,20}` 误解为"可有可无"就可能漏);`'  alice  '` 带空格返回 false(对,但 AI 没解释"为什么空格算非法"——是 \w 不含空格,这点要写注释);最关键的是 `'a'.repeat(20)` 与 `'a'.repeat(21)` 的边界——AI 写 `{4,20}` 没问题,但若把它写成 `{4, 20}`(带空格)在某些正则引擎里是合法的、在另一些里会报错,AI 不会主动提。

更隐蔽的是 Unicode 陷阱。`/^[a-zA-Z0-9_]{4,20}$/` 在 JavaScript 里默认按 UTF-16 码元计数,`'café'` 长度是 4(é 是单码元),但 `'小明'` 长度是 2、`'𝕏'`(U+1D54F,超出 BMP)长度是 2(代理对占两个码元)。如果你的产品真的想"允许 Unicode 字母",AI 写的这个正则是错的,得用 `/^[\p{L}\p{N}_]{4,20}$/u`(带 u 标志,用 Unicode 属性转义)。AI 不会主动问"你要不要支持国际化用户名",得你来决策——这就是判据二(选型)在前端的具象。

补完边界后的版本:

```javascript
function validateUsername(name) {
  if (typeof name !== 'string') return false;
  const trimmed = name.trim();
  if (!trimmed) return false;             // 空值/全空白
  // 仅允许 ASCII 字母数字下划线,长度 4-20(按 UTF-16 码元)
  return /^[A-Za-z0-9_]{4,20}$/.test(trimmed);
}
```

这个版本能交吗?写法可交,但"是否支持 Unicode 字母""超长怎么提示""是否要做防注入"这些选型必须你来拍。AI 写出来的正则只是起点,边界用例是终点,中间的判断是你的责任。

### 3. 让 AI 写 CSS 动画,核对 transform / opacity

让 AI 写"卡片 hover 时浮起 + 阴影加深"的动画。AI 交回来:

```css
.card {
  transition: all 0.3s ease;
}
.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
```

这句 `transition: all` 是 AI 的常见偷懒写法。它会让所有属性都过渡,包括 `box-shadow`——而 `box-shadow` 不在合成层属性里,改它要重绘,大量卡片同时 hover 时帧率会掉。第 06 篇讲过重排最贵、重绘中等、合成最便宜;`transform` 走合成,`box-shadow` 走重绘,二者混在一个 `all` 里等于把合成的便宜和重绘的中等捆在一起。

修正版:

```css
.card {
  transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1),
              box-shadow 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
  will-change: transform;
}
.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
```

把 `all` 拆成显式属性、用缓动曲线代替 `ease`、加 `will-change` 提示浏览器提升图层。这版能跑且性能合理。验 收 用 Chrome DevTools 的 Performance 面板录一段 hover 动画,看 Paint 时间——`transition: all` 版本在 50 张卡片同屏时 Paint 可能 12ms,显式版本能压到 4ms 以内,差距在一帧之内决定 60fps 是否达成。

这里 AI 写的语法对、动画也能播,但性能取舍要你来定。`will-change` 不能滥用(常驻会让 GPU 内存涨),`box-shadow` 在大列表里要不要换成 filter 也得看场景。AI 不会替你做这种"看场景的取舍",这正是判据二(选型)在动画上的体现。

### 4. 让 AI 写完整页面模板,核对可访问性

让 AI 基于 Tailwind 写一个登录页。AI 交回的初版往往是这样的(节选):

```html
<form class="max-w-sm mx-auto mt-20 p-6 rounded shadow">
  <input type="text" placeholder="用户名" class="w-full mb-4 p-2 border rounded">
  <input type="password" placeholder="密码" class="w-full mb-4 p-2 border rounded">
  <button class="w-full bg-blue-600 text-white p-2 rounded">登录</button>
</form>
```

视觉上没问题。但这份代码漏了 Accessibility 的几条硬约束:input 没有 `label`(屏幕阅读器读不出字段名)、button 没有 `type="submit"`(在 form 内默认是 submit,但显式写更安全)、错误提示没有 `aria-live`(出错了视障用户感知不到)。AI 在写模板时倾向"看着对",很少主动加 a11y 属性。

补完 a11y 的版本:

```html
<form class="max-w-sm mx-auto mt-20 p-6 rounded shadow" novalidate>
  <div class="mb-4">
    <label for="login-user" class="block mb-1 text-sm">用户名</label>
    <input id="login-user" type="text" required
           autocomplete="username"
           class="w-full p-2 border rounded">
  </div>
  <div class="mb-4">
    <label for="login-pwd" class="block mb-1 text-sm">密码</label>
    <input id="login-pwd" type="password" required
           autocomplete="current-password"
           class="w-full p-2 border rounded">
  </div>
  <p id="login-err" role="alert" class="hidden text-red-600 text-sm mb-2"></p>
  <button type="submit" class="w-full bg-blue-600 text-white p-2 rounded">登录</button>
</form>
```

`label[for]` 绑定 input、`role="alert"` 让错误提示被屏幕阅读器即时播报、`autocomplete` 帮密码管理器识别字段。这些属性不影响视觉但影响可达性,AI 不会主动加——这正是第 06 篇"语义化"在模板层的延续,也是判据一(识错)的延伸:你心里得有"正确模板长什么样",才能比对出 AI 漏了什么。

### 5. 让 AI 写 Sass / Less 预处理代码

CSS 预处理器是 AI 的强项。让 AI 把一个设计系统的颜色和断点写成 Sass 变量与 mixin,AI 一遍过:

```scss
// design-tokens.scss
$breakpoints: (
  sm: 480px,
  md: 768px,
  lg: 1024px,
  xl: 1280px,
);

$colors: (
  primary: #2563eb,
  primary-hover: #1d4ed8,
  text: #1f2937,
  muted: #6b7280,
);

@mixin respond-to($name) {
  @if map-has-key($breakpoints, $name) {
    @media (max-width: map-get($breakpoints, $name)) {
      @content;
    }
  } @else {
    @error "未知断点: #{$name}";
  }
}

.button {
  background: map-get($colors, primary);
  color: white;
  @include respond-to(sm) {
    width: 100%;
  }
}
```

这份代码基本可交,编译产物符合预期。需要你审的只有两点:`@error` 分支在生产编译时是否会因笔误炸掉 CI(写法层错误,显性);断点用 `max-width` 还是 `min-width`(选型,取决于移动优先还是桌面优先的策略)。Sass 的变量、mixin、嵌套都是规范化的样板,AI 写错的概率低,识错成本低,是可交一侧最稳的部分。

## 四、速查/自测

### 速查表:前端"可交 vs 必审"对照

| 工作类型 | 可交 / 必审 | 关键判据 | 风险点 |
|---|---|---|---|
| 精美页面样式 | 可交 | 识错零成本(浏览器一开就见) | 漏浏览器兼容、漏 box-sizing |
| 响应式媒体查询 | 可交 | 选型不依赖业务(行业惯例断点) | 漏极小屏断点、漏 minmax(0,1fr) |
| transition / animation | 可交 | 识错零成本(动画播不播、卡不卡) | `transition: all` 拖性能、动 left 触发重排 |
| Tailwind / Ant Design 模板 | 可交 | 识错零成本(视觉对不对) | 漏 a11y 属性、漏 label |
| 表单校验正则 | 可交(写法) | 写法显性;选型(Unicode 与否)必审 | 漏空值、漏 Unicode、漏超长边界 |
| Autoprefixer 前缀 | 可交 | 工具自动 | 漏目标浏览器配置 |
| Sass / Less 预处理 | 可交 | 编译时错误显性 | 断点策略 max/min 选型 |
| SVG 图标代码 | 可交(图形) | 视觉验收 | 漏 `role="img"`、漏 `aria-label` |
| 闭包 / 定时器清理 | 必审 | 隐性泄漏,卸载后才爆 | AI 不主动 clear |
| this 指向 / 原型链 | 必审 | 隐性,运行时才错 | `==` 隐式转换、浅拷贝 |
| z-index 层叠上下文 | 必审 | 隐性,特定滚动位置才错 | 父元素形成上下文压住子元素 |
| CORS 预检配置 | 必审 | 隐性,本地能跑上线报错 | 漏 OPTIONS 中间件 |

### 自测题

1. **原理层**:为什么 CSS 动画可交、JavaScript 闭包动画要审?
   <details><summary>参考答案</summary>
   CSS 是声明式,状态由关键帧描述、由浏览器合成,没有悬挂的执行路径,错误在视觉层显性;JavaScript 是命令式,闭包持有引用、回调有排队顺序,组件卸载后定时器或监听器仍可能持有引用造成泄漏,失效是隐性的。"错误是否隐性"是分界线。</details>

2. **思路层**:AI 写的响应式卡片在 320px 下溢出,你怎么定位到 `min-width:auto` 这条根因?
   <details><summary>参考答案</summary>
   先 DevTools 选中 grid 容器看 computed width,发现超出视口;再选中卡片看 min-width,默认值是 auto,意味着卡片不会缩到内容宽度以下;内容里的长单词或图片撑开卡片,grid 的 1fr 算法尊重 min-width,于是撑爆容器。修复把 `1fr` 换成 `minmax(0, 1fr)`,允许卡片缩到 0。这条根因不在 AI 的初版里,因为 AI 不知道你的内容会不会撑爆。</details>

3. **实践层**:让 AI 写一个邮箱校验正则,你列出至少四个边界用例,说明每个用例在测什么。
   <details><summary>参考答案</summary>
   空 `''`(测空值)、`'a@b.c'`(测最短合法)、`'a'.repeat(64) + '@b.c'`(测超长,本地段 RFC 上限 64)、`'用户@例子.中国'`(测 Unicode,看是否支持国际化域名)、`'a@b'`(测无 TLD,看是否要求顶级域名)、`'a@b.c d'`(测尾随空格)。每个用例对应一条业务约束,这些约束 AI 不会主动问,必须你定。</details>

4. **实践层**:AI 交回的卡片 CSS 里有 `transition: all 0.3s ease`,你怎么判断要不要改?
   <details><summary>参考答案</summary>
   看过渡属性里有没有重绘或重排属性。`all` 把 transform(合成,便宜)、box-shadow(重绘,中等)、color(重绘)都捆在一起,同屏卡片多时帧率会掉。改成显式列出 `transform, box-shadow`,用 `cubic-bezier` 替代 `ease`,必要时加 `will-change: transform`。判断依据是同屏元素数量:单个卡片 `all` 可接受,列表里几十张就要拆。</details>

5. **原理层**:为什么"触摸目标 ≥ 44px"是 AI 写卡片时最常漏的约束?
   <details><summary>参考答案</summary>
   44px 来自 iOS HIG 与 WCAG 2.5.5 的可达性建议,是物理尺寸(约 9mm 指尖)而非视觉尺寸。AI 默认桌面审美,按"看着合理"设 padding,不会主动把触摸目标当硬约束。这是判据一(识错)的延伸:你心里得有"移动端正确卡片长什么样",才能比对出 AI 漏了 min-height。可交的是写法,必须懂的是可达性约束。</details>

## 可交给 AI 的部分

本章里能放心交给 AI 的,是"写法层与样板层":响应式卡片的 grid 布局代码、媒体查询断点定义、transition 与 keyframes 语法、Tailwind / Ant Design / Element 的完整模板、表单校验正则初版、UI 组件的 JSX / Vue SFC 初版、Autoprefixer 生成的兼容性前缀、Sass / Less 的变量与 mixin。这些共同特征是:错误在视觉层显性、选型不依赖隐性业务上下文、定位有明确报错或视觉差异。交给 AI 时只要配好验收用例(Playwright 断点回归、Performance 面板录帧、a11y 自动扫描),三轮内能收敛到正确代码。

交给 AI 时的风险有四条,恰好对应前端可交工作的四类常见缺陷:

- **浏览器兼容风险**:AI 写的 CSS 常漏移动端 WebView 兼容,尤其新特性(`gap` in flex、`:has()` 选择器、`aspect-ratio`、容器查询 `@container`)。AI 不会主动查 Caniuse,你得在 PR 里跑一遍 browserslist 覆盖检查,或在 Playwright 里跑 Safari iOS、小米浏览器内核的真机回归。
- **JavaScript 隐性坑**:即便主体是 CSS,AI 写的交互 JS 可能有原型链 / 闭包坑——`Object.assign` 浅拷贝、`==` 隐式转换、定时器未 clear、事件监听未 removeEventListener。这些 bug 语法对、运行也对、卸载十秒后才爆,属于第 06 篇内核层的范畴,必须自己审。
- **表单边界风险**:AI 写的正则默认 happy path,漏空值、Unicode 字母、超长输入、代理对计数四类边界。AI 不会主动问"要不要支持国际化用户名",你得把边界用例写进测试,让 AI 的代码去匹配用例,而不是让用例去迁就 AI 的代码。
- **SVG 可访问性风险**:AI 生成的 SVG 图标常漏 `role="img"`、`aria-label`、`<title>` 子元素,视障用户读不到。装饰性 SVG 还应加 `aria-hidden="true"`。AI 不会主动区分"装饰"还是"信息",这条选型必须你来定。

判断标准只有一条:涉及"长什么样、什么动画、什么布局、什么正则"时,大胆交给 AI 并配验收用例;涉及"何时执行、谁持有引用、谁盖住谁、谁允许谁访问、谁能读到"这五类隐式行为时,自己过一遍原理。前一半是本章的范围,后一半是第 06 篇的范围,合起来才是完整的前端知识边界。

## 参考来源

- [1] Eric A. Meyer、Estelle Weyl:《CSS权威指南》(CSS: The Definitive Guide)第5版 2024
- [2] MDN Web Docs:《响应式设计》(developer.mozilla.org/zh-CN/docs/Learn/CSS/CSS_layout/Responsive_Design)
- [3] MDN Web Docs:《使用媒体查询》(developer.mozilla.org/zh-CN/docs/Web/CSS/CSS_media_queries/Using_media_queries)
- [4] W3C CSS Grid Layout Module Level 1(含 minmax 与 min-width:auto 规范)(w3.org/TR/css-grid-1/)
- [5] Tailwind CSS 官方文档:响应式设计前缀 sm/md/lg/xl(tailwindcss.com/docs/responsive-design)
- [6] Caniuse 浏览器兼容性查询表(caniuse.com)
- [7] W3C Web Content Accessibility Guidelines (WCAG) 2.1,Success Criterion 2.5.5 Target Size(w3.org/TR/WCAG21/#target-size)
- [8] Apple Human Interface Guidelines:Touch Targets(developer.apple.com/design/human-interface-guidelines/buttons)
- [9] Autoprefixer 官方文档与 browserslist 配置(github.com/postcss/autoprefixer)
- [10] Playwright 官方文档:视口与设备模拟(playwright.dev/docs/emulation)
- 本专栏第 02 章「知识边界的第一性原理」(三条判据识错/选型/定位,本文将其反推到前端可交工作的判定)
- 本专栏第 06 章「三件套必须掌握的内核」(闭包、this、事件循环、层叠上下文、重排重绘等必须掌握的内核,本文为其互补篇)
