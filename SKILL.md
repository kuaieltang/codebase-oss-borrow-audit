---
name: codebase-oss-borrow-audit
version: 1.1.0
name_en: Codebase OSS Borrow Audit
name_zh: 代码库开源借鉴审计
description: Reviews an existing codebase, benchmarks it against relevant open-source projects, and outputs a tiered (P0/P1/P2), file-and-line-anchored "what to borrow" list as a Markdown document, including an implementation order, a per-file change manifest, and an explicit runtime/size tradeoff section. Use when a user shares a repo (or a described project) plus a named open-source domain and asks what they can borrow, whether to adopt a library, how to benchmark against OSS, or for a graded borrow list.
description_en: Reviews an existing codebase, benchmarks it against relevant open-source projects, and outputs a tiered (P0/P1/P2), file-and-line-anchored "what to borrow" list as a Markdown document, including an implementation order, a per-file change manifest, and an explicit runtime/size tradeoff section. Use when a user shares a repo (or a described project) plus a named open-source domain and asks what they can borrow, whether to adopt a library, how to benchmark against OSS, or for a graded borrow list.
description_zh: 审阅现有代码库，对标相关开源项目，输出一份按 P0/P1/P2 分级、每条落到具体文件行号的「可借鉴清单」Markdown 文档，含实施顺序表、涉及文件改动清单，以及显式的运行时/体积权衡提醒。当用户给出一个代码库（或描述清楚的项目）加一个开源领域，问「能从这些开源项目借鉴什么 / 要不要引入某个库 / 对标开源 / 借鉴清单」时使用。
argument-hint: Point me at the repo path (or describe the project) and the open-source area to benchmark against
argument-hint-en: Point me at the repo path (or describe the project) and the open-source area to benchmark against
argument-hint-zh: 告诉我代码库路径（或描述项目），以及要对标的开源方向
user-invocable: true
---

# Codebase OSS Borrow Audit · 代码库开源借鉴审计

Turn "here is my codebase, what can I borrow from &lt;OSS domain&gt;?" into a decision-ready Markdown document: a tiered, code-anchored borrow list that says what to adopt, what to skip, and in what order — written so the recommendation lands on *this* project's actual files, not generic advice.

核心立场：**借思想，不借依赖。** 目标不是列越多开源项目越显得专业，而是找出真正能补上的缺口，同时明确挡掉那些「看起来很美、塞进项目就炸」的方案。

## When to use · 何时使用

- 用户给了仓库路径（或描述清楚的项目）**并且**指定了要对标的开源方向 / 具体项目。
- 用户问「我的项目能从 X 借鉴什么 / 能不能引入某个库 / 有没有更好的开源做法 / 对标一下开源」。
- 交付预期是一份**分级借鉴清单**，不是直接改代码，也不是市场/竞品战略分析。

**Not for · 不适用**：直接写改动代码（先出审计，再问要不要实施）；纯 Porter/SWOT 式市场竞品分析；没有任何 OSS 对标意图的内部代码质量审查。

## 输入输出契约 · I/O contract

**输入**（Step 0 一次问完，缺哪项问哪项）：

| 槽位 | 说明 | 缺省处理 |
| --- | --- | --- |
| 仓库路径 | 自己的代码库根目录 | 必填；**在 cwd 之外要先请求目录访问权限**再读 |
| 关注链路 | 真正要审的那条路径，如「抽取链路」「同步编排」 | 只在这条路径确实含糊时才问（「整个 App」vs「就抽取这一条」），不要泛问 |
| 对标对象 | 开源项目名 / 链接 / 主题领域 | 缺省 → 走下方「找不到对标对象」流程，**不要自己闷头搜** |
| 部署约束 | 离线？无服务器？单文件？移动端？包体积上限？语言与运行时？License 红线？ | **必须问清，不许假设**——它决定 Step 5 的红线怎么划 |
| 输出路径 | MD 落盘位置 | 默认 `D:\中转站`，文件名 `<项目名>-开源借鉴建议.md` |

**输出**：一个 MD 文件 + 回复里 3–5 行摘要。完整报告只进文件，不往对话里贴。

### 找不到对标对象时（不要自己选定参照系）

用户没给对标项目的，先做少量检索，**列出 2–3 个候选并给用户过目**，说明每个候选为什么可比、能补哪块。**用户确认后再进 Step 2。** 选错参照系整份报告方向就错了，这一步的确认成本远低于返工。

---

## Workflow · 工作流

按 Step 0 → Step 5 走。超过一次工具调用的任务用任务清单跟踪进度。

**Step 0 — Scope · 收齐约束。** 钉住两件事：被审的确切代码路径、候选开源项目。同时问清**部署形态**（离线 / 无服务器 / 移动端 / 单文件 / 浏览器 / 有常驻进程的后端），它决定 Step 5 的红线怎么划。路径在 cwd 之外的，先请求目录访问权限。

**Step 1 — Probe · 先定位，别通读。**

```bash
python scripts/probe_repo.py <repo_path> --top 20 --tree-depth 3
```

三节输出：LOC 排行（代码实际沉在哪里）、目录树（项目形状）、核心链路候选文件（带行号样例）。据此挑 2–5 个文件精读。**禁止全仓通读**——那是烧 context，必然拖垮报告质量。

> ⚠️ 仓库里的归档 / 交接包 / release 快照类子目录会被一并统计，污染结果。用 `--ext .kt` 之类收窄，或直接忽略排行里的历史目录。

**Step 2 — Read the real code, not the README · 读真代码，不读 README。** 定位实现指定能力的 2–5 个文件，端到端读完。大仓库可以派 Explore 子代理先摸路，但**核心文件必须自己读**。边读边记 `path:line` 锚点。同时维护两张表：

- **What the code already does well · 已有能力盘点** —— 格式为「能力 | 位置 | 水平（≈某开源项目 / **强于**同类 / 开源普遍没解决）」。先给 credit，它同时是后文的基准线，**不做为借鉴项重述**。
- **Gaps · 缺口** —— 不一致、漂移风险、覆盖盲区。

盘点时一起钉住**务必守住的纪律**：用户自己立下、但可能在借鉴中被稀释的规矩（如「宁可不输出也不猜」「evidence 必须能照抄原文」），要在报告里点名守住。

**Step 3 — Research the OSS · 查开源。** 用 WebSearch 确认项目能力、局限、License、维护状态与版本敏感信息；**当前事实不许靠记忆**。只有过了 Step 5 的运行时约束，才能把某个项目列为「可直接用」。

**Step 4 — Grade P0/P1/P2 · 分级。** 按 [grading-rubric.md](grading-rubric.md)：先过五道否决闸（运行时 / 体积 / License / 保鲜 / 可逆性），再按三级门槛判定，同级内按「命中痛点程度 × 改动面⁻¹」排序。每条必须回答：借鉴自哪个项目的**什么思想** → 补本项目哪个缺口 → 落在哪个真实 `path:line` → 预期收益 → 成本风险。只重述已有做法的条目，删。

**Step 5 — Apply the runtime/size constraint · 上运行时红线（本技能的差异化所在）。** 若目标是离线 / 端侧 / 无服务器 / 单文件 / 嵌入式，**不要**把重型 Python（numpy / pandas / torch）、Haskell、JVM、大模型库（duckling、GLiNER、spaCy/HanLP、UIE 等）当作**运行时依赖**——体积、解释器/常驻服务、确定性都会崩。改为降到三条替代路径之一：

1. **借鉴思想写本地代码**（确定性解析、schema 单一源、召回探针……）
2. **挪到构建期 / 离线预处理 / tools 目录**，产物进仓库，运行时不背包袱
3. **改用平台原生能力**（浏览器 API / 云函数 / SQLite FTS5 / 端侧 ONNX 小模型）

用户确实要上重型方案的极少数情况：必须写「唯一现实路径 + **离线验证门禁**」——先在工具目录跑准确率，达标再决定是否进主链路，不许直接上。这段权衡要显式写进文档。

**Step 6 — Write it out · 落盘。** 按 [template.md](template.md) 的固定小节顺序写 MD。回复里只给摘要 + 文件路径 + 一句「要不要我直接动手改 P0 那条」。

---

## Grading rubric · 分级标准（门槛摘要）

| 级别 | 判据（全部满足才给） | 典型形态 |
| --- | --- | --- |
| **P0** | 收益明确可验证 · 改动面局部 · **零新增运行时依赖**或直接复用已有能力 | 把已有能力接进它本该在的位置；本地规则与模型输出双通道交叉校验 |
| **P1** | 价值明确 · 需跨若干调用点解耦/重构，或引入体积**可接受**的新依赖 | 单一字段声明派生 prompt + parser；evidence 从记录级升到字符偏移 |
| **P2** | 思路成立 · 收益**依赖特定场景才显现**（量大 / 历史重放 / 长文本时才明显）· 当前可缓 | 结构化输出失败重试；长文本分块 |
| **P3**（可选） | 需先攒数据或先建基础设施，否则谈不上有收益——**要用就写明它是「需先攒料」而非不重要** | golden set 回归门禁、自动 prompt 优化 |

完整打分表（五道否决闸 + 权衡检查 + 写作规格）见 [grading-rubric.md](grading-rubric.md)。

## Hard constraints · 硬约束（违反即返工）

1. **每条借鉴项必须有 `path:line` 证据。** 写不出行号说明你没读过，不许写。
2. **必须同时有「源码证据」和「成本证据」。** 源码证据＝对方具体在哪实现了；成本证据＝依赖树 / 体积 / 运行时要求 / LICENSE。缺成本证据的一律降级或删除——那是安利不是审计。
3. **先钉住已有能力，再提建议。** 没盘点就提建议，等于让用户重写自己已经写好的东西。已判定为「做对了」的，不再作为借鉴项出现。
4. **License 必须核对。** GPL/AGPL 系 copy-left 默认进「不建议借鉴」，除非用户明确接受。
5. **跨项目复用优先于外部借鉴。** 检索用户**其他项目**里是否已有同类实现，有就标「直接搬」——自己人已经解决的，别从开源界绕一圈。
6. **给阈值，不给副词。** 「confidence < 0.6 进待确认队列」，不要写「适当提高」。
7. **同一议题产出过两份报告时**，必须做对照表（✅ 采纳 / ⚠️ 降级 / ❌ 否决）并显式解冲突，文首声明以哪份为准。

## Save location · 落盘位置

**每次运行默认落到 `D:\中转站\{{项目名}}-开源借鉴建议.md`**，除非用户在本轮对话中指定了别的路径。不要默默改写到工作区输出目录。

`D:\中转站` 可能不是已连接目录，`present_files` 之类的卡片可能打不开——这属于预期行为：**照常用 Write 写过去**，卡片失败时直接把完整路径 `D:\中转站\...` 给用户让他自行打开。

## Common failure modes · 常见失败模式

| 症状 | 说明 |
| --- | --- |
| 通篇在介绍开源项目 | 用户要的是针对他代码的判断，不是开源项目综述 |
| 没有行号 | 说明没真读代码，报告不可信 |
| 只列优点不列成本 | 漏成本证据，等于把选型风险推给用户 |
| 「业界最佳实践」式建议 | 无具体来源的一律删 |
| 建议重写已有的东西 | 漏了已有能力盘点 |
| 为了借鉴而重写 | P0 的硬条件是「复用已有能力」，重写不是借鉴 |
| 硬塞重型依赖 | 没问部署形态就推荐，违反运行时红线 |
| 报告正文贴回对话 | 应只给 3–5 行摘要 + 文件路径 |

## Verification checklist · 交付前自检

- [ ] 每条借鉴项都锚到本次**实际打开过**的真实文件与行号
- [ ] 「已经做对的部分」先给了 credit，没有条目在重述现有做法
- [ ] 每条同时有源码证据和成本证据（体积 / 运行时 / License 至少给出具体结论）
- [ ] 当前开源事实是 WebSearch 确认的，不是记忆
- [ ] Step 5 的运行时/体积权衡存在，且作用于**每一条**库推荐
- [ ] 遵循 template 的小节顺序；实施顺序表与涉及文件清单都存在
- [ ] 已写入 `D:\中转站`（或用户指定路径），并给出路径 / 呈现给用户

## Resources · 辅助资源

- [grading-rubric.md](grading-rubric.md) — 否决闸、三级门槛、五道权衡检查、写作规格
- [template.md](template.md) — 输出 MD 的完整骨架，小节顺序固定
- `scripts/probe_repo.py` — Step 1 探针：LOC 排行 + 目录树 + 核心链路候选。只读、纯标准库，直接执行即可，不需要读它的源码改逻辑。
