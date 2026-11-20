# 28: 非自愿式纯机械波及闸门筛选与重跑机制

**What to build:** 基于 `codebase-design` 深模块原则，新增纯机械的改动波及分析模块（`zreflect/impact.py`）并接入 `zreflect/registry.py`（`--affected`）与 `zreflect/harness.py`（`--affected`），根据 `git diff`（或注入的变更路径列表）+ 静态 AST import 反向依赖图 + `GATE = meta(knobs=...)` 声明自动计算必须重跑的闸门与 `--selftest` 集合；任何无法机械证明无波及的变更（核心模块、全局配置、未知路径或 `git` 读取失败）保守退化为全量重跑。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/impact.py --selftest && python3 zreflect/registry.py --selftest && python3 zreflect/harness.py --selftest -- rc=0 => pure mechanical affected-gate planner, registry --affected, harness --affected and cross-gate run cache pass; rc!=0 => impact regression

## 设计约束（`codebase-design`）

1. **单一深模块与小接口（Deep Module / Small Interface）**：
   - **Module**：`zreflect/impact.py`（需要同时在 `zreflect/registry.py` 的 `MODULE = ...` 登记），把 AST 反向依赖构图、knob→路径映射、保守退化判定全藏在实现内部。
   - **Interface**：只暴露极简纯函数入口（如 `affected_plan(changed_paths, phase_gates, zdir=..., knobs=...) -> dict`），**接收依赖、返回结果、不产生副作用**；CLI/hook 适配器在 `registry._main_run` 与 `harness.py` 的接缝（seam）处把 `git status`/`git diff` 注入进去，测试可直接注入 `changed_paths` 列表实现零 IO 单测。
2. **非自愿式、纯机械筛选（无人工白/黑名单逃逸口）**：
   - 不提供“手动指定跳过某闸门”或“手动声明某文件安全”的开关；筛选结果完全由以下三项机械推导：
     - **静态 AST import 图**：扫描 `zreflect/*.py` 的 `import` / `from ... import ...`（含传递依赖），计算每个 `.py` 文件的反向波及闸门集；改 `gate.py`/`i18n.py`/`knobs.py`/`doc.py`/`seal.py`/`registry.py` 等公共底座时自动扇出到全部依赖闸门。
     - **闸门声明与 `knobs` 路径映射**：从 `GATE = meta(knobs=...)` 与 `knobs.REGISTRY` / `knobs.json` 推导每个闸门读取的输入面（`REFLECT_DOCS`、`REFLECT_QUESTIONS`、`REFLECT_RETRACTIONS`、`REFLECT_READMES`、`REFLECT_LANGS`、`ruff.toml`、`secrets.json`、`examples/*` 等）。
     - **保守闭环退化（Fail-closed）**：修改 `knobs.json`、`SEAL.json`、`reflect-hooks/*`、`.github/*`、未知根目录文件或 `git` 不可用时，机械标记 `full_fallback=True` 并选中全部可运行闸门，绝不静默漏跑。
3. **接入接缝与可观测输出**：
   - `zreflect/registry.py` `--run <phase>` 默认启用机械 `--affected` 筛选（`--all` 才跑全量，取代初版显式 `--affected` 开关），`zreflect/harness.py --affected` 在同一个接缝调用 `impact`，并在输出中明确打印选中原因（命中闸门数 / 总闸门数，或 `full_fallback` 原因），杜绝把局部验证伪装成全量通过。
   - `zreflect/check_facts_replay.py` 与 `zreflect/check_questions.py` 在单次 `registry --run` 生命周期内可共享纯只读子进程命令结果缓存，避免同一检查命令在原则与悬案之间重复冷启动。

## 复跑方式

```sh
python3 zreflect/impact.py --selftest && python3 zreflect/registry.py --selftest && python3 zreflect/harness.py
```
