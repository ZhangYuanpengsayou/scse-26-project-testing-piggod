# 2026-10-18 验证修复与 VIVA 补充

这份文件记录对旧项目的修复和真实运行证据。旧版复习总册第 1–16 章保留历史状态；当前操作方式见 [README](README.md)。
最终运行状态以 [artifacts/latest_run.json](artifacts/latest_run.json) 及其指向的运行目录为准，不能只看文件是否存在。

## 这次修了什么

| 旧问题 | 当前处理 |
|---|---|
| Analyst/Planner 连接失败仍读取旧 JSON | 在线流程失败即报告，不静默复用 |
| Developer/Test Agent 异常时返回固定代码 | 移除静默替代，保留真实请求、响应和错误 |
| JSON 结构正确就算有效 | 排除目标占位文字，检查安全布尔值、七条有序决策 |
| 生成测试但不执行 | 子进程实际收集测试、执行断言、检查退出码与覆盖状态 |
| 测试代码本身可能错误 | 独立合同检查；只有原版满足合同，才允许有限次数的测试代理修复 |
| 修改后可能仍导入原版 | 显式注入被测候选模块，报告记录 SHA-256 |
| 修订只写文件、不重新评估 | 同一套测试及四世界 benchmark 分别检查原版与修订版 |
| 有“通过”输出，但不知测试能否抓错误 | 故意破坏副本，要求断言失败，再运行原版确认通过 |
| 覆盖旧日志，难以解释来源 | 每次独立运行目录、源文件快照、旧产物备份和原始模型记录 |

模型调用超时、截断或结构不合格都不等于模型生成成功。调用记录的 `received` 也只代表收到内容；还必须通过内容和行为验证。

测试文件是“模型生成的测试函数与断言 + 框架补齐的固定导入”。`test_agent.py` 解析 AST 后，只在缺少依赖时补充 `product` 和 `decide_next_move` 的导入，不替换断言。原始响应与组装后的源码均保留，不能把固定导入也说成模型原样生成的内容。

## 五星：必须讲清楚

### 1. 文件生成、程序结束、行为通过是三件事 ★★★★★

`created` 只说明文件被写出。`Pipeline completed` 只说明控制流走到了最后。
可靠的成功判定需要检查测试结果、退出码、报告字段、具体候选版本和最终验证门槛。

**英文答法：** Creating a file is not evidence that it works. We execute the tests, check their exit codes and coverage, and associate each report with the exact candidate version.

### 2. 测试也可能有 bug ★★★★★

本次真实生成的测试曾把 `FORWARD` 拆成传感器字段，出现 `IndexError`；另一次使用了不存在的 `FORWARD_blocked`，出现 `KeyError`。
真实字段是 `front_blocked`。动作名称与传感器字段属于不同命名体系，应使用明确映射，而不是猜测字符串规律。

不是一看到测试红了就改导航代码。先用独立检查器确认问题属于测试还是被测实现。原版通过 64 个布尔状态和 8 个省略目标字段状态后，才允许把测试执行报错交给 Test Agent 修复，最多生成三次。
通过后固定测试，不在修订导航时放宽断言。

**英文答法：** A failing test can reveal a bug in the implementation or in the test itself. We use an independent contract checker before allowing bounded repairs to generated tests.

### 3. 64 个状态代表什么 ★★★★★

六个布尔字段各有两种取值，所以共有 `2 ** 6 = 64` 种组合。三个可选目标字段省略后，还有 `2 ** 3 = 8` 种障碍物组合需要单独检查。
把目标字段设置为 `False`，不等于省略这个字段；这两种输入可以触发不同的 Python 行为。
执行器记录导航函数实际收到的不同状态，而不只相信测试源码声称“覆盖全部情况”。

### 4. 变异测试为什么重要 ★★★★★

在隔离副本里把“全部方向被挡住时 STOP”故意改成 FORWARD。
正确版本应通过，错误副本必须因断言失败被抓到，再次检查正确版本仍通过。
这能证明测试对这个特定错误敏感，不证明它能抓住所有错误。真实文件不需要被破坏后再恢复。

### 5. 修订为什么不一定让步数变少 ★★★★★

修订可以改善异常输入处理而不改变正常路径。此次评审明确增加防御性要求：输入不是字典，或缺少任意一个障碍物字段时停止。
这是在原始六布尔合同之外增加的健壮性要求，不能伪称原始 brief 已经要求全部异常输入。
如果原版和修订版在四个正常世界中的步数相同，不必编造效率提升；应展示实际改善的边界行为。

### 6. 为什么仿真不需要一直启动 Qwen ★★★★★

Qwen 用于开发阶段生成需求、计划、Python 导航代码、测试和修订代码。
机器人运行时执行的是已生成的 `decide_next_move(state)`，不是每一帧请求语言模型。
因此离线重测现有代码可以不启动 Ollama；重新生成则需要服务可用。

### 7. 这是完整自主 Agent 吗 ★★★★★

这是固定流程、多角色的开发工作流，包含有限的反馈修复。两个 Reviewer 是确定性规则程序。
不要把它描述成所有组件都使用 LLM、无限自主规划、RAG 或 fine-tuning 系统。

## 四星：结合源码理解

- **HTTP 与异常：** Python 标准库请求本机 Ollama；连接拒绝、超时、截断、JSON 无效是不同错误，不应混成成功。
- **AST：** 解析 Python 语法，检查函数结构；变异实验通过语法树改函数名。AST 检查不是恶意代码安全沙箱。
- **子进程：** 新进程隔离候选导入、设置超时、收集 stdout/stderr；进程返回 0 仍需检查测试数量和结果。
- **模块导入：** 老版仿真脚本固定导入 `generated.navigation_logic`；外层执行器把指定候选放进模块表，使原版与修订版都能使用未改动的老师脚本。
- **哈希与可追溯性：** SHA-256 用来关联源码和报告，不是对程序正确性的证明。
- **JSON 与日志：** JSON 便于程序读取指标，trace 便于按时间理解执行过程；两者应一起检查。
- **固定合同：** 安全目标方向优先，其次按 FORWARD、LEFT、RIGHT 选择安全方向；全部受阻才 STOP。多目标标志同时为真时，也需要明确优先级。

## 仍然不能过度宣称的事情

四个固定世界成功不等于所有地图都安全，六布尔逻辑检查也不是实物机器人验证。
老师脚本的 `collision_or_done` 合并了碰撞和终止，不能把它当成精确、独立的碰撞测量。
转向锁定、简化障碍物感知、更多传感器故障和随机场景仍是后续验证范围。
本次修改不代表已经提交或推送到了 GitHub。

## 最终实测记录

**最终结论：在以下明确的检查范围内，真实生成、执行测试、仿真、评审、修订和复测已经形成闭环。不是仅凭 `Pipeline completed` 得出的结论。**

完整在线运行：`20261018T133807-399993`，Analyst、Planner、Developer、Test Agent、Developer Revision 五个阶段都有真实 Qwen 请求与响应。
这次运行通过了当时的检查，但人工追加 `42` 后发现第一版修订仅检查 `None`，没有覆盖其他非字典输入。因此又进行了追加复核。

最终复核：`20261018T135019-595370`。它是明确记录来源的 `review_continuation`，不是再次调用全部五个阶段：沿用并校验上次的需求、计划、原版代码和固定测试，重新调用 Qwen 修订，并重新执行原版和新修订版的全部测试与仿真。
原版、最终修订版都与各自保存的模型响应一致；测试与“原始模型响应 + 已说明的固定导入组装”一致。检查见 [final_artifact_audit.json](artifacts/final_artifact_audit.json)，17 项一致性检查全部通过。

| 验证项目 | 原版 | 最终修订版 |
|---|---:|---:|
| Qwen 生成的三个测试函数 | 通过 | 通过 |
| 实际覆盖的完整布尔状态 | 64 / 64 | 64 / 64 |
| 省略目标字段的障碍物组合 | 8 / 8 | 8 / 8 |
| 独立合同检查 | 通过 | 通过 |
| 追加的异常/不完整输入检查 | 0 / 12 | 12 / 12 |
| IR-SIM 到达目标 | 4 / 4 | 4 / 4 |
| 满足 200 步效率阈值 | 4 / 4 | 4 / 4 |
| 平均步数 | 169.5 | 169.5 |

12 项异常输入检查是新增的防御性扩展，不应把原版在这一行的失败混淆为原始六布尔合同失败。

| 世界 | 原版步数 | 修订版步数 |
|---|---:|---:|
| easy | 150 | 150 |
| medium | 148 | 148 |
| hard | 187 | 187 |
| custom | 193 | 193 |

这次修订改善的是接口健壮性，没有测得正常路径的步数提升。关键新增防护为：

```python
if not isinstance(state, dict):
    return 'STOP'
if not all(k in state for k in ['front_blocked', 'left_blocked', 'right_blocked']):
    return 'STOP'
```

其他实测结果：

- [流程回归测试](artifacts/pipeline_integrity_report.json)：19 / 19 通过，使用标准库 unittest；其中的 mock 用于测试错误处理，不能当作真实模型调用证据。
- [变异实验](artifacts/mutation_report.json)：正确修订版通过，故意改错副本被断言抓住，重新检查正确修订版通过，真实候选文件哈希未变。
- [最终发布文件复测](artifacts/final_revised_tests_check.json)：仓库 `generated/` 中的修订版也通过，不仅是运行目录里的临时版本通过。
- 老师提供的 `test_irsim_with_agent.py` 与 `run_visual.sh` 未修改。
- Ollama 本次使用 CPU、4 线程、每次调用后卸载模型；结束后的 `/api/ps` 返回空模型列表。没有更改系统自启动设置，也没有声称修好了硬件/驱动故障。
- 本机未安装 pytest，实际验证使用 unittest 和项目执行器；`pytest.ini` 仅为将来使用 pytest 时排除历史快照。

### 怎样查证

1. 先读 [最新运行摘要](artifacts/latest_run.json)，确认 `status=passed` 和 `mode=review_continuation`。
2. 根据 `source_run` 查 [完整在线运行](artifacts/runs/20261018T133807-399993/run_summary.json)，其 `model_calls/` 有五个真实生成阶段。
3. 查 [最终复核运行](artifacts/runs/20261018T135019-595370/run_summary.json)，其 `model_calls/` 有本次真实修订调用，`previous_revision_audit.json` 保留上一版类型问题的证据。
4. 对照 `initial/`、`revised/` 的测试、simulation、benchmark 和 review 文件。每个世界有单独的原始报告与 stdout/stderr。
5. 检查 `mutation/` 中正常、错误副本和恢复后的报告。不能把 `baseline.json` 误认为最初的导航版本：它是变异实验中尚未破坏的正确修订版。

### 失败尝试也保留了

`artifacts/runs/` 中保留了目标占位文字、规划漏项、测试输出截断、错误字段名以及测试代理重试失败的尝试。这些 `interrupted` / `failed` 记录不算成功证据。
单独的 Test Agent smoke 检查位于 `artifacts/test_agent_smoke/`，也不能冒充完整流水线运行。不要在 VIVA 中说项目第一次生成就全部正确。

### 更新后的英文口述

> We completed a live Qwen generation workflow and then an explicitly traced review continuation. The same generated test suite checks both navigation versions across 64 Boolean states and eight states without goal flags. Both versions reached the goal in all four IR-SIM worlds, with an average of 169.5 steps. A follow-up review found incomplete type handling, so we asked Qwen to revise it again. The final version passed twelve defensive-input checks. We also deliberately broke a copy and confirmed that assertions detected the error. These results support the tested scope, not a claim of universal robot safety.
