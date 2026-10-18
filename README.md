# SCSE Robot Navigation Project

本项目把需求分析、规划、代码生成、测试生成、仿真、评审和修订整合为一个可追踪流程。
Analyst、Planner、Developer、Test Agent、Developer Revision Agent 调用本机 Qwen。
两个 Reviewer 使用明确的 Python 规则，不是 LLM；IR-SIM 运行生成的 Python 导航函数，不逐帧调用模型。

2026-10-18 已完成实际在线生成和追加修订复核，结果、来源与 VIVA 答法见 [验证记录](VERIFICATION_NOTES.md)。

## 环境与运行

使用 Python 3.12。下面是本机验证时的依赖版本；已有环境无需重复安装：

```powershell
python -m pip install -r requirements.txt
ollama list
python -X utf8 -m unittest test_pipeline_integrity -v
python -X utf8 -u main.py
```

完整流程需要本机 Ollama 服务监听 `127.0.0.1:11434`，并已安装 `qwen3:8b`。
未启动时可手动打开 Ollama，或在独立终端运行 `ollama serve`，无需开启系统自启动。
此项目通过标准库 HTTP 调用 Ollama，不依赖 Python 的 `ollama` 包。

`model_client.py` 默认串行 CPU 推理、4 线程、关闭 thinking、每次调用后释放模型。
这是针对本机过去运行 Ollama 不稳定的保守配置，不保证排除硬件/驱动故障。
不要同时启动多次 `main.py`。模型调用可能需要数分钟；模型未连接、输出截断或验证失败均会报错，绝不静默换用旧产物。

已有完整成功记录后，追加评审可显式指定来源，例如：

```powershell
python -X utf8 -u main.py --review-run artifacts/runs/20261018T133807-399993
```

这是 `review_continuation` 模式，**不是重新在线生成所有阶段，也不是连接失败后的 fallback**。
它核对来源运行的状态、候选/测试哈希、brief 和世界文件，沿用冻结的需求、计划、原版代码与测试，并记录 `source_run` 和 `reused_artifact_sha256`。
它再调用 Qwen 生成修订版，重新执行两版测试与全部世界仿真。该模式不允许重新生成或放宽冻结的测试。
默认不带此参数的 `main.py` 仍是从头真实调用全部生成阶段的 `strict_live` 模式。

## 怎么判断真的通过

首先看 `artifacts/latest_run.json` 中的 `status`，然后检查其指向的运行目录。
只有 `passed` 才表示修订版通过当前检查。`failed` / `interrupted` 不能当成功提交证据。
即使旧的根目录报告显示成功，也不能覆盖最新运行的失败状态。

每次完整运行在 `artifacts/runs/<运行编号>/` 中保存：

- `model_calls/`：本次实际调用的请求、响应、模型名称、推理参数和错误。完整模式包含五个模型阶段；追加评审模式的复用阶段应沿 `source_run` 查原始证据。`received` 只说明收到响应，不代表内容验证通过。
- `source_snapshot/`：运行时 Python 源码、brief 和世界文件；`run_summary.json` 保存源码 SHA-256。
- `previous_outputs/`：覆盖前的旧文件，包括旧日志和旧导航代码。
- `requirements.json`、`plan.json`、原版/修订版导航代码、Qwen 生成的测试文件。
- `initial/` 与 `revised/`：分别针对指定候选代码执行测试、64 状态检查、四世界 IR-SIM 和规则评审。
- 每个世界的独立工作目录、原始仿真报告、完整 stdout/stderr；报告记录候选代码和世界文件的哈希。
- `revision_request.json`：原版的真实测试/评审结果及修订要求。
- `mutation/`：正确版本通过、故意改错的副本失败、再次运行正确版本通过的证据。

通过后才发布根目录 `generated/` 和主要 `artifacts/` 文件。未加 `revised_` 前缀的报告对应原版，带此前缀的报告对应修订版。
`generated/navigation_logic.py` 保留原版，`generated/navigation_logic_revised.py` 保留修订版，不相互覆盖。
根目录 `irsim_report.json` 仅是原版最后一个世界的单次结果，完整证据应看 benchmark 报告。

## 验证为什么可信一些

1. 测试文件不仅生成，还会在独立 Python 进程中收集并执行所有零参数 `test_*` 函数。
2. 没收集到测试、测试未实际调用全部 64 个布尔状态和 8 种省略目标字段的状态、断言失败、超时或进程异常退出，都不能通过。
3. 独立逻辑检查器按“安全候选集合、目标优先、固定顺序”计算预期，且检查函数没有修改输入。
4. 同一份生成的测试同时检验原版与修订版，不通过修改测试去迎合修订结果。
5. 变异实验只修改隔离副本：全部方向受阻时错误返回 FORWARD。必须被断言抓到，而非因导入错误失败。
6. `candidate_worker.py` 在新进程里显式注入指定候选模块，让未改动的老师仿真脚本也能运行修订版。
7. benchmark 检查退出码、报告存在性和关键字段，逐世界隔离，防止误读上次报告。

生成的测试也可能有 bug。测试函数和断言来自 Qwen；`test_agent.py` 通过 AST 检查并补齐两个固定依赖导入，不改写模型生成的断言。原始模型响应与最终组装文件都保留，可以对比。

只有当独立检查器确认原版通过 64 个布尔状态及 8 个省略目标字段状态时，流程才允许测试代理根据真实报错重新生成测试（总计最多三次）。每次源文件与执行结果都会保留。通过预检查后固定测试文件，导航修订阶段不再改变它；不允许为了迁就错误导航代码而放宽标准。模型连接失败、输出截断等调用级错误仍直接终止流程。

## 修订的实际含义

即使原版的标准场景已通过，也会请求一次真实模型评审后修订，并重新测试。
这不意味着虚构一个 benchmark 错误。评审额外检查了防御性接口行为：输入不是字典，或缺少任一障碍物字段时应 STOP。
这是明确标注的健壮性扩展，不是声称原始 brief 已要求这些异常输入。
当前检查 12 种异常/不完整输入，包括 `None`、缺字段字典、整数、浮点数、布尔值、列表和字符串。只判断 `state is None` 不足以保护所有非字典输入。
正常状态仍按安全目标方向 FORWARD、LEFT、RIGHT 优先，再按安全方向 FORWARD、LEFT、RIGHT 回退。
目标字段可以省略；到达终点由仿真器判断。修订必须保持全部合法状态的行为。

## 离线重测已生成代码

下面不需要启动 Ollama，不会重新生成代码：

```powershell
python -X utf8 -m unittest test_pipeline_integrity -v
python -X utf8 test_generated_navigation_logic.py
python -X utf8 candidate_worker.py tests generated/navigation_logic_revised.py test_generated_navigation_logic.py --report artifacts/manual_revised_tests.json
python -X utf8 -c "from benchmark_irsim import run_benchmark; from pathlib import Path; print(run_benchmark(Path('generated/navigation_logic_revised.py'), Path('artifacts/manual_revised_benchmark')))"
```

`test_analyst.py`、`test_planner.py`、`test_developer.py` 是早期手动在线 smoke 脚本，会覆盖相应根目录产物。
正式留证据请用 `main.py`，不要在完整流程运行时并行运行它们。
默认验证使用标准库 `unittest` 和自带执行器，本机未安装 `pytest`。如另行使用 pytest，仓库的 `pytest.ini` 会排除历史运行快照，避免把归档测试当作当前测试收集。

## 边界与答辩诚实表述

- 通过 64 状态不等于穷尽真实世界；四个固定世界的一次结果也不证明所有地图都安全。
- 提供的模拟器含转向锁定和简化障碍检测。`collision_or_done` 是合并终止信号，不能当作独立的精确碰撞指标；规则评审中的 safety 只能理解为该仿真代理指标。
- 静态 AST 检查是有限的代码审查辅助，不是恶意代码安全沙箱。生成的代码应先审查，子进程主要用于隔离导入和限制运行时间。
- 不是 RAG 或 fine-tuning 系统，也不是导航时持续调用 LLM 的自主机器人。
- 变异实验能证明测试抓住了这个特定错误，不等于完整 mutation score 或全部错误覆盖。
- 提交前核对最新运行状态、原版与修订版源码、所有 artifacts 和评审记录。代码尚未自动提交或推送到 GitHub。
