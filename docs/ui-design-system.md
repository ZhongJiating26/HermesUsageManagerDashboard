# 浅紫数据工作台 UI 设计规范

版本：1.0 · 整理日期：2026-10-20 · 来源：Hermes Usage Manager 当前前端源码。

用途：把当前网站的视觉语言迁移到其他管理后台、数据平台和工具网站。本文可以独立交给设计师、前端开发者或 AI 建站工具使用，业务名称、菜单和数据均可替换。

本文中的颜色、尺寸和行为以源码为准；“迁移建议”是面向新网站的补充，不代表当前项目已经实现。参考图用于理解整体构图，不用截图估算值覆盖源码值。

## 1. 风格定义

**一句话：以白色为画布、低饱和浅紫为容器、深紫为操作强调，搭配大圆角、胶囊控件和轻量图表的 Material Design 3 倾向数据工作台。**

这里的 Material Design 3 是视觉方向，当前项目使用自定义 CSS，并非完整的官方组件库或完整 MD3 Token 实现。

| 维度 | 规范 |
|---|---|
| 气质 | 安静、柔和、清晰、理性，适合持续阅读与数据扫描 |
| 层次 | 用白色、近白紫、浅紫、深紫的色阶区分画布、卡片、选中态、操作 |
| 形状 | 卡片与面板大圆角，按钮与筛选胶囊形；内容区域保持规整 |
| 密度 | 页面留白充足，表格与图表标签紧凑，重点数字突出 |
| 立体感 | 普通卡片平面呈现；弹窗、抽屉、说明浮层使用轻阴影 |
| 主次 | 先看标题和核心数字，再看趋势、分布，最后看明细 |

保留这套设计的关键是“浅紫容器 + 深紫操作 + 圆润几何 + 克制层次”，不只是把按钮改成紫色。迁移时保持纯色表面、轻分隔和少量强调，避免为普通卡片增加厚重阴影或装饰渐变。

## 2. 颜色规范

### 2.1 核心颜色

| 语义 | 色值 | 当前变量 / 用途 |
|---|---|---|
| 主色 Primary | `#6750A4` | `--hum-primary`；主按钮、选中分段、文字操作、进度条 |
| 主色浅容器 | `#E8DEF8` | `--hum-container`；导航选中、表头、分段底色、徽标 |
| 卡片表面 | `#FAF6FC` | `--hum-surface`；卡片、表格主体、输入框、空状态 |
| 弱表面 | `#F3EDF7` | `--hum-muted`；弱按钮；独立版顶栏也使用此色 |
| 主文字 | `#1D1B20` | `--hum-text`；正文、标题、核心数字 |
| 次级文字 | `#625F68` | `--hum-secondary`；说明、标签、辅助信息 |
| 轻边框 | `#E8E0ED` | `--hum-border`；表单边框、分隔、弹窗边框 |
| 白色画布 | `#FFFFFF` | 主工作区背景、弹窗、浮层、对话内容区 |
| 侧栏 / 独立版底色 | `#F6F1FA` | 侧栏；独立版页面底层与登录背景 |

色彩层次：白色画布 → `#FAF6FC` 卡片 → `#E8DEF8` 选中容器 → `#6750A4` 操作焦点。普通卡片使用填色区分层级，默认无描边、无阴影。

### 2.2 辅助颜色与状态

| 语义 | 色值 | 使用位置 |
|---|---|---|
| 导航文字 | `#48424F` | 未选中导航 |
| 选中浅底上的文字 | `#4D3680` | 徽标；导航选中仍沿用导航文字 |
| 分段未选中文字 | `#5D4B78` | 分段控件、页签 |
| 弱说明 | `#817989` | 分类标题、元信息、细小标签 |
| 表头文字 | `#332B3D` | 表头 |
| 表格文字 | `#746D7B` | 表格内容 |
| 表格分隔线 | `#EEE6F7` | 行底边 |
| 表格悬停 | `#F0E9F8` | 行悬停背景 |
| 成功标记 | `#69746C` | 列表成功状态图标 |
| 成功反馈 | `#3C6B4E` | 操作完成提示文字 |
| 错误 | `#B3261E` | 失败标记、错误提示 |
| 键盘焦点 | `#8468C4` | 3px 外轮廓，偏移 3px |
| 对话抽屉底色 | `#FCF9FF` | 抽屉背景 |
| 对话气泡 | `#E9DDFC` | 用户与助手消息气泡 |
| 对话正文 | `#494250` | 气泡内容 |

状态必须同时有文字或图标表达。成功、失败、未知等语义不能仅依赖颜色。迁移建议：小字号弱文字和相近紫色色阶在新场景中需要重新检查对比度，本文不等同于无障碍合规认证。

### 2.3 数据可视化配色

分类系列按以下顺序取色，保持同一数据维度在不同图表中的颜色一致（跨图一致性为迁移建议，当前代码按系列顺序取色）：

```text
#6750A4  #8268B9  #9980D0  #B3A0E2
#CBBBF4  #DDD2FA  #A896D0  #E7DFF6
#85749F  #A49CAF  #D0C7DC  #F0E9FA
```

| 场景 | 颜色 |
|---|---|
| 缓存输入 / 未缓存输入 / 输出堆叠 | `#CBBBF4` / `#9980D0` / `#6750A4` |
| 概览用量趋势 | `#8B87E8` |
| 活跃人数趋势 | `#B1CF19`，少量黄绿色用于区分第二指标 |
| MCP 趋势 | `#8268B9`，面积透明度 `0.16` |
| 默认排行柱 | `#9980D0` |
| 排行轨道底色 | `#F2ECF8` |
| 轴标签 / 网格线 | `#77717E` / `#E4DFEB` |
| 饼图引导线 | `#C9C3CF` |

黄绿色是图表中的辅助对比色，不作为常规主按钮颜色。多类别数据需配合图例、标签、数值和悬浮信息，避免仅靠相近的紫色色块辨认。

## 3. 字体与排版

字体栈：

```css
font-family: system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
```

| 层级 | 字号 / 字重 | 规则 |
|---|---|---|
| 基础正文 | 14px / 400 | 全局行高 1.55 |
| 页面标题 h1 | 22px / 600 | 行高 1.4，无默认外边距 |
| 卡片标题 h2 | 14px / 600 | 通常下间距 12px，卡片工具栏内为 0 |
| 次级标题 h3 | 13px / 浏览器默认粗体 | 上下间距 12px / 4px |
| 弹窗标题 | 20px / 600 | 抽屉摘要标题为 22px，窄屏 19px |
| 导航项 | 13px | 选中项 600 |
| 表格 / 筛选说明 | 12px | 保持紧凑 |
| 次级说明 / 图表标签 | 10–12px | 主体以 11px 为主 |
| 核心 KPI | 32px / strong 默认粗体 | 右对齐，字距 -1px；≤1150px 时 26px |

标题使用适度加粗，不使用全页粗体。单位用小字号和次级文字色，与大数字保持主次。当前数字格式：缺失值为 `—`；普通数值使用千分位；图表可使用 K/M 等紧凑表示；费用显示明确币种，当前业务为 USD。

迁移建议：密集数据列可以增加 `font-variant-numeric: tabular-nums`；移动端正文和可操作标签可按新产品可读性要求放大，不必机械保留 10–11px。

## 4. 布局、间距与形状

### 4.1 桌面骨架

```text
白色工作区：padding 28px，横向 gap 32px
├─ 左侧导航：宽 224px，浅紫底，圆角 18px
└─ 内容区：flex: 1，min-width: 0，max-width: 1440px
   ├─ 页面标题 + 说明入口 / 右侧状态徽标
   ├─ 筛选工具栏：筛选项在左，日期组靠右，可换行
   └─ 内容堆栈：gap 14px
      ├─ KPI：3 等列，共用一个圆角容器
      ├─ 趋势：通栏卡片
      ├─ 分布：2 等列，gap 12px
      └─ 排行或明细表
```

当前侧栏为普通文档流，`align-self: flex-start`，顶部偏移 `62px`，不是固定或粘性导航。内容区未强制水平居中。新站可按自己的顶栏调整这两个位置规则，保留导航与内容的比例和留白即可。

### 4.2 尺寸基准

| 对象 | 当前数值 |
|---|---|
| 根容器 | padding 28px；gap 32px；圆角 20px |
| 页面标题区 | 下间距 24px；子元素 gap 16px |
| 普通卡片 | padding 20px 22px；圆角 18px |
| 卡片标题行 | 最小高度 28px；gap 10px |
| 工具栏 / 筛选栏 | gap 12px；筛选栏下间距 18px |
| 导航容器 | padding 18px 12px；圆角 18px |
| 导航项 | padding 13px 16px；图标间距 14px；圆角 28px |
| 表格外容器 | 圆角 18px；横向滚动 |
| 页签 | 整体圆角 24px；按钮 padding 10px 20px |
| 徽标 | padding 5px 12px；圆角 20px；11px / 600 |

间距主节奏来自 8、12、16、20、24、28、32px，源码也包含 10、14、18、22px 等局部值。迁移建议：把常用间距收敛为 Token，不把当前项目描述为严格统一的 4px 或 8px 网格。

圆角按语义选择：大容器 18–24px，普通控件约 22px，胶囊选择器 `999px`，人员列表项 9px，提示浮层 12px，登录卡片 28px。抽屉贴边，使用直角。

## 5. 组件规范

### 5.1 按钮与筛选

| 类型 | 样式 |
|---|---|
| 主按钮 | 深紫底、白字；无边框；圆角 22px；padding 10px 20px |
| 描边按钮 | 透明底、1px 深紫边框、深紫字；用于次级操作和分页 |
| 文字按钮 | 透明底、深紫字；padding 5px 8px；圆角 6px |
| 普通输入 | 近白紫底、1px 轻边框；圆角 22px；padding 9px 14px |
| 下拉选择 | 自定义向下箭头、胶囊外形；右侧预留 36px |
| 强调筛选 | 深紫底、白字白箭头；当前用于部门、人员、日期等筛选 |
| 搜索框 | 浅紫底、圆角 24px；搜索图标与输入间距 8px |
| 复选框 | 20 × 20px，accent-color 为主色 |

交互状态：按钮悬停 `filter: brightness(.96)`；禁用 `opacity: .45` 且鼠标为 `not-allowed`；键盘焦点为紫色外轮廓。当前源码没有独立的全局按下态 Token。

分段控件：浅紫轨道，选中为深紫胶囊与白字，未选中为紫灰字。小型图表分段按钮为 11px，padding 5px 13px。页面页签保持同一种选中逻辑，但字号和内边距更大。

### 5.2 卡片与 KPI

- 普通卡片使用 `#FAF6FC`，靠底色与留白建立边界。
- 卡片标题靠左，帮助图标紧邻标题，指标切换放右侧。
- KPI 为一个三列容器，列间用 1px 边框色分隔，内部 padding 20px。
- KPI 名称在上、大数字靠右、单位弱化；细分信息用小字和 5px 进度条表示。
- 卡片内部避免多层重复边框，图表直接放入卡片。

### 5.3 表格与分页

表头浅紫、表体近白紫，单元格以细横线分隔，无纵向网格。表头 padding `15px 18px`，内容 padding `13px 18px`，字号 12px。默认左对齐、内容不换行；悬停行使用 `#F0E9F8`。明细表最小宽度 960px，在外容器横向滚动。

可点击字段保留明确的交互入口，例如时间、名称、ID；排序箭头放在列标题旁。分页在表格下方右对齐，包含总数、每页条数、前后页按钮和深紫页码胶囊，默认提供 20 / 50 / 100 条选择。

迁移建议：数值列可右对齐；长名称截断时提供完整内容入口。排序、分页、筛选变更需要保持当前数据范围清晰。

### 5.4 弹窗、抽屉与帮助浮层

| 对象 | 当前规格 |
|---|---|
| 普通弹窗 | 宽 `min(760px, 100vw - 32px)`；最大高度 85vh；padding 24px；圆角继承根容器 20px |
| 普通弹窗阴影 / 遮罩 | `0 16px 80px #21152B38` / `#21152B55` |
| 右侧详情抽屉 | 宽 `min(760px, 100vw)`；高 100dvh；无圆角；底色 `#FCF9FF` |
| 抽屉阴影 / 遮罩 | `-12px 0 40px #21152B12` / `rgb(29 27 32 / 40%)` |
| 抽屉内边距 | 上 20px、左右 28px、下 22px |
| 帮助浮层 | 宽 280px；padding 14px 16px；圆角 12px；白底、轻边框 |
| 帮助浮层阴影 | `0 4px 20px #21152B20` |

弹窗采用原生 `dialog` 模态行为，支持 Escape 关闭并在关闭后还原触发前焦点。抽屉打开时锁定背景滚动，摘要与关闭入口保持在上方，对话区独立滚动。帮助入口可点击展开说明，内容过长时浮层内部滚动。

### 5.5 对话与工具详情

助手消息靠左、用户消息靠右；两者均为浅紫气泡，以位置和角色标签区分。气泡最大宽度 82%，padding `14px 18px`；助手左上角直角，其余 24px，用户右上角直角，其余 24px。

消息间距 30px，角色和时间为 11px 次级文字。文本长度超过 320 字符或超过 6 行时，初始折叠为 4 行，可展开完整内容。连续工具调用组成浅灰圆角组，内部每个工具为白色圆角项，支持两级展开，标题显示次数与状态。

### 5.6 图标与反馈状态

图标使用本地 Material Symbols 字体，默认 22px，导航图标区域 20px，帮助图标 19px；局部关闭与箭头使用 SVG / CSS。迁移时保持同一图标体系，图标跟随文字色，并为纯图标按钮提供可访问名称。

空状态：近白紫容器、圆角 18px、padding `56px 24px`，中央放轻量图标、说明和下一步建议。加载状态：同色系骨架块；骨架填色为 `#F0E9F8 → #E8DEF8 → #F0E9F8` 的静态渐变。错误状态提供明确说明和重试按钮。

## 6. 图表规范

- 当前使用 ECharts SVG 渲染，图表宽度随容器变化。
- 默认高度 300px；主趋势 320px；用户排行 360px；工具排行 480px。
- 隐藏轴线和刻度线，保留浅色网格；轴标签通常 11px，图例通常 10–11px。
- 趋势使用平滑折线；堆叠柱最大宽度 44–50px；排行柱最大宽度 18px，右侧圆角 4px。
- 饼图半径为容器可用尺寸的 58%，中心位于 50% / 46%，图例在底部；保留外部标签和引导线。
- 分类饼图展示前 9 项，剩余合并为“其他”；过长图例可滚动。
- 图表交互可下钻明细，底部提供可展开的数据列表，支持查看数值和筛选。
- 当前更新动画 250ms；系统启用减少动态效果时关闭图表动画。
- 折叠箭头旋转过渡 150ms；其他组件未定义统一全局动效规范。

迁移时保持单位、图例和数据范围可见；未知值继续显示缺失状态，不把缺失当成零。新业务若有不同语义，应重新分配系列名称，保留色彩和线条的视觉规则。

## 7. 响应式规范

以下宽度均为视口宽度断点：

| 条件 | 当前变化 |
|---|---|
| ≤1150px | 根 padding / gap 均为 20px；导航宽 190px；KPI 数字 26px；人员分配区域收紧 |
| ≤850px | 双列图表变单列；KPI 变单列；人员分配三栏变单栏 |
| ≤680px | 根容器纵向排列，padding 14px、gap 12px、圆角 14px；显示移动导航按钮，侧栏默认收起 |
| ≤680px | 标题纵向排列；日期组取消靠右；卡片 padding 16px 10px；页签 padding 9px 14px |
| ≤680px | 抽屉全宽，padding 14px 12px；消息最大宽度 92%；摘要和工具列表缩小内边距 |
| ≤600px | 独立版顶栏水平 padding 16px；登录卡片 padding 24px |

当前桌面表格在窄屏保持横向滚动。迁移建议：在新网站验收长标题、长 ID、筛选换行和图表标签，确保主操作始终可触达。

## 8. 独立网站外壳

独立版沿用同一主题：页面底层 `#F6F1FA`，顶部栏 `#F3EDF7`，主工作区白色且边缘无圆角。顶栏为 13px，padding `10px 28px`；顶栏按钮为浅紫底、深紫字、圆角 24px。

登录页内容居中：白色卡片最大宽度 360px，padding 36px，圆角 28px，阴影 `0 12px 40px #6750A414`；字段纵向 gap 18px。新站可以替换站点名称、身份信息与登录方式。

## 9. 可复制的主题 CSS

以下是从现有样式抽取并重新命名的跨站起步样式，包含核心视觉规则，不是项目全部样式的逐行副本。将根类 `.lavender-ui` 放在新网站主题容器上；弹窗若通过 Portal 挂载，也应放在此主题作用域内或单独继承这些变量。

```css
.lavender-ui {
  --ui-primary: #6750a4;
  --ui-on-primary: #fff;
  --ui-container: #e8def8;
  --ui-surface: #faf6fc;
  --ui-muted: #f3edf7;
  --ui-sidebar: #f6f1fa;
  --ui-text: #1d1b20;
  --ui-secondary: #625f68;
  --ui-border: #e8e0ed;
  --ui-error: #b3261e;
  --ui-focus: #8468c4;
  --ui-radius-card: 18px;
  --ui-radius-pill: 999px;
  color: var(--ui-text);
  background: #fff;
  font: 14px/1.55 system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
}
.lavender-ui, .lavender-ui * { box-sizing: border-box; }
.lavender-ui .ui-layout { display: flex; gap: 32px; padding: 28px; }
.lavender-ui .ui-sidebar {
  width: 224px; flex-shrink: 0; align-self: flex-start;
  padding: 18px 12px; border-radius: 18px; background: var(--ui-sidebar);
}
.lavender-ui .ui-main { flex: 1; min-width: 0; max-width: 1440px; }
.lavender-ui h1 { margin: 0; font-size: 22px; line-height: 1.4; font-weight: 600; }
.lavender-ui h2 { margin: 0 0 12px; font-size: 14px; font-weight: 600; }
.lavender-ui .ui-stack { display: flex; flex-direction: column; gap: 14px; }
.lavender-ui .ui-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.lavender-ui .ui-card {
  min-width: 0; padding: 20px 22px;
  border-radius: var(--ui-radius-card); background: var(--ui-surface);
}
.lavender-ui button, .lavender-ui input, .lavender-ui select { font: inherit; }
.lavender-ui .ui-button {
  border: 0; border-radius: 22px; padding: 10px 20px;
  background: var(--ui-primary); color: var(--ui-on-primary);
  cursor: pointer; white-space: nowrap;
}
.lavender-ui .ui-button--outline {
  border: 1px solid var(--ui-primary); background: transparent; color: var(--ui-primary);
}
.lavender-ui .ui-button--text {
  background: transparent; color: var(--ui-primary); padding: 5px 8px; border-radius: 6px;
}
.lavender-ui button:hover { filter: brightness(.96); }
.lavender-ui button:disabled { opacity: .45; cursor: not-allowed; }
.lavender-ui :is(button, input, select, summary):focus-visible {
  outline: 3px solid var(--ui-focus); outline-offset: 3px;
}
.lavender-ui input, .lavender-ui select {
  min-width: 0; max-width: 100%; border: 1px solid var(--ui-border);
  border-radius: 22px; padding: 9px 14px;
  background: var(--ui-surface); color: var(--ui-text);
}
.lavender-ui .ui-table-scroll { overflow-x: auto; border-radius: 18px; background: var(--ui-surface); }
.lavender-ui table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; white-space: nowrap; }
.lavender-ui th { padding: 15px 18px; background: var(--ui-container); color: #332b3d; font-weight: 500; }
.lavender-ui td { padding: 13px 18px; border-bottom: 1px solid #eee6f7; color: #746d7b; }
.lavender-ui tbody tr:last-child td { border-bottom: 0; }
.lavender-ui tbody tr:hover { background: #f0e9f8; }
@media (max-width: 1150px) {
  .lavender-ui .ui-layout { gap: 20px; padding: 20px; }
  .lavender-ui .ui-sidebar { width: 190px; }
}
@media (max-width: 850px) {
  .lavender-ui .ui-grid { grid-template-columns: 1fr; }
}
@media (max-width: 680px) {
  .lavender-ui .ui-layout { flex-direction: column; gap: 12px; padding: 14px; }
  .lavender-ui .ui-sidebar { display: none; width: 100%; }
  .lavender-ui .ui-sidebar[data-open="true"] { display: block; }
  .lavender-ui .ui-card { padding: 16px 10px; }
}
```

移动导航开关、选中状态、下拉箭头、弹窗、图表和无障碍语义需由新站按本文组件规范补齐；上述 CSS 不包含这些完整行为。

## 10. 交给其他网站或 AI 工具的复用提示词

复制以下内容，并将方括号中的内容替换为目标网站需求：

> 为「[网站名称与用途]」实现一套浅紫数据工作台风格 UI。视觉方向为 Material Design 3：白色主画布、低饱和紫色表面、深紫交互强调、圆角卡片、胶囊按钮、轻分隔线和克制阴影。
>
> 核心颜色：主色 #6750A4，主色浅容器 #E8DEF8，卡片 #FAF6FC，弱表面 #F3EDF7，侧栏 #F6F1FA，主文字 #1D1B20，次级文字 #625F68，边框 #E8E0ED，错误 #B3261E。主按钮深紫底白字，选中导航浅紫底深色字，选中分段深紫底白字。普通卡片无阴影，浮层按需使用轻紫灰阴影。
>
> 字体使用 system-ui / Segoe UI / Microsoft YaHei。正文 14px、行高 1.55，页面标题 22px/600，卡片标题 14px/600，核心数字 32px，辅助标签 11–12px。桌面页面 padding 28px、导航宽 224px、导航与正文 gap 32px，正文最大宽 1440px；卡片圆角 18px、padding 20px 22px，内容纵向 gap 14px、双列网格 gap 12px。按钮 padding 10px 20px、圆角 22px，下拉筛选为胶囊形。
>
> 页面内容按「标题与帮助 → 筛选 → 关键指标 → 趋势 → 分布 / 排行 → 明细」组织，依据业务需要选用。表格表头 #E8DEF8、主体 #FAF6FC，仅使用浅色横向分隔线；行悬停 #F0E9F8。图表使用同一紫色色阶，辅助对比线可用 #B1CF19，隐藏轴线与刻度线，使用浅色网格和底部图例。
>
> 在 1150px 收紧留白，在 850px 将双列和 KPI 改为单列，在 680px 收起侧栏并显示导航开关，表格横向滚动。交互包含悬停、选中、禁用、可见键盘焦点、加载、空状态、错误与重试。弹窗与抽屉需支持键盘关闭、焦点管理；尊重系统减少动态效果设置。
>
> 将业务内容替换为「[目标页面、菜单、字段和操作]」，保留以上颜色角色、布局节奏、圆角层级和交互语言。缺失数据有明确占位，状态同时提供文字或图标。完成后检查桌面和移动端布局、文字可读性与主操作的可触达性。

## 11. 迁移验收清单

- [ ] 白色、近白紫、浅紫、深紫分别承担画布、卡片、选中容器、主操作角色。
- [ ] 页面、卡片、控件的圆角和内外间距保持本文层级。
- [ ] 字体、标题、核心数字、说明形成稳定的阅读顺序。
- [ ] 导航、分段、按钮、输入框、表格、弹窗使用同一种视觉语言。
- [ ] 图表颜色、单位、图例清晰，相近色仍有标签或数据入口辅助辨认。
- [ ] 加载、无数据、失败、禁用、键盘焦点均有可理解的状态。
- [ ] 窄屏下卡片改单列、导航可打开、表格可滚动、长文本不撑破布局。
- [ ] 已根据目标网站检查对比度、触控尺寸和键盘操作；未把原项目尺寸当成合规结论。

## 12. 源码依据与参考图

以下路径相对于本仓库根目录；把本文单独复制到其他网站时，无需依赖这些文件即可使用前面的规范。

| 文件 | 提供的依据 |
|---|---|
| `frontend/src/theme.css` | 核心配色、字体、布局、全部主要组件、响应式断点 |
| `frontend/src/standalone.css` | 独立版顶栏、画布和登录页 |
| `frontend/src/Dashboard.tsx` | 导航、标题、筛选与页面骨架 |
| `frontend/src/components/chart-options.ts` | 图表调色板、坐标轴、图例、柱宽、饼图与排行 |
| `frontend/src/components/EChart.tsx` | SVG 渲染、自适应、动画与减少动态效果 |
| `frontend/src/components/common.tsx` | 空状态、加载错误、分页、弹窗行为与数值格式 |
| `frontend/src/components/SessionDetails.tsx` | 对话角色、长文折叠、工具详情与滚动结构 |
| `references/` | 项目原始原型图，辅助理解视觉构图 |

概览原型（用于整体构图参考，非当前运行截图）：

![概览原型](../references/概览.png)
