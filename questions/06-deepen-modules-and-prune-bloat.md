# 06: 深化单向深模块 DAG、合并语言包分片与钩子入口、淘汰自指元警察与 100% 纯 Python 化

**What to build:** 在保留全部 `check_*` 业务闸门语义、`PRINCIPLES.md`/`STATE.md`/`questions/` 三载体分工、零语言核心（`en`/`zh`/`de`）与 `SEAL.json` 硬校验的前提下，消除循环依赖、冗余元警察、碎模块、99 个语言包小分片以及残余 shell 依赖，并一并修复下游实操暴露的 `knobs.json` 旁路与性能瓶颈：
1. 删除 `zreflect/criteria.py`、`zreflect/ledger.py`、`zreflect/living.py`、`zreflect/runner.py`、`zreflect/machine.py`、`zreflect/echoes.py`、`reflect-hooks/install.py`、`reflect-hooks/quality-record.sh`（及 `examples/echoes/`、`examples/quality_record/`、`.shellcheckrc`、`gitroll-dispositions.json`、`zreflect/*.json.example`）。
2. 建立严格单向依赖 DAG：`knobs.py`（Layer 0，零本地 import）→ `i18n.py`（Layer 1，吸收 `machine.py` + 合并 `zreflect/lang/{en,zh,de}.json` 为 3 个单文件，并将语言包同步/覆盖校验迁回 `check_i18n.py`）→ `gate.py`（Layer 2，吸收 `runner.py`、`exec_position_problems`、通用 `run_spec_gate()` 与 `sha256_file()`）→ `seal.py` / `doc.py` / `registry.py`（Layer 3）→ `facts.py`（Layer 4，吸收 `ledger.py`、`living.py`、`block_homes()` / `doc_block_problems()`）。
3. 将 `reflect-hooks/install.py` 合入 `reflect-hooks/hook.py`，实现套件 100% 纯 Python（CI 移除 `shellcheck`）。
4. 修复 15 处绕过 `knobs.json` 的 `os.environ.get("REFLECT_*")`、解耦 `REFLECT_NO_PRINCIPLES=1` 与 `REFLECT_DOCS`、清理 `doc.RULES` 重复执行面与 `OFF:` 冲突、修复 `facts.py --accept` 整数与 `[[key]]` 校验/`next.py` 空分支/`questions/01-example.md` 状态，并将 `facts.py --selftest`、`check_facts_replay.py` 与 `harness.py` 提速至秒级。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Settling:** python3 -c "import os,sys; gone=('zreflect/criteria.py','zreflect/ledger.py','zreflect/living.py','zreflect/runner.py','zreflect/machine.py','zreflect/echoes.py','reflect-hooks/install.py','reflect-hooks/quality-record.sh','.shellcheckrc','gitroll-dispositions.json','examples/echoes','examples/quality_record','zreflect/lang/en','zreflect/lang/zh','zreflect/lang/de'); packs=('zreflect/lang/en.json','zreflect/lang/zh.json','zreflect/lang/de.json'); sys.exit(0 if (not any(os.path.exists(p) for p in gone) and all(os.path.isfile(p) for p in packs)) else 1)" && python3 zreflect/registry.py --verify-seal && python3 zreflect/registry.py --run commit && python3 zreflect/harness.py —— rc=0 ⇒ 碎模块、自指元警察、99 语言包目录与残余 shell 已收敛完毕，三份单文件语言包就位，且封签与全量闸门/自证全绿；rc≠0 ⇒ 仍有待删模块/目录残留或校验未通过

## 锁定边界（不可改动）

- **保留全部业务闸门语义与三分载体**：保留 `check_ab`、`check_explain`、`check_facts`、`check_facts_replay`、`check_history`、`check_i18n`、`check_instruments`、`check_invariants`、`check_lint`、`check_locks`、`check_pins`、`check_questions`、`check_readme_sync`、`check_retractions`、`check_secrets`、`check_snapshots`、`check_stale`、`check_world`、`doctor` 全部 19 道闸门的核心判定契约与可配置关停语义，保留 `PRINCIPLES.md` / `STATE.md` / `questions/` 分工。
- **保留零语言核心与三语包**：`M(code, **params)` 在无语言包时输出机器码；`en` / `zh` / `de` 语言包保持等键等价与占位符校验。
- **保留 `SEAL.json` 硬校验**：核心共享模块、内置闸门、单文件语言包与 `ruff.toml` 继续受 `zreflect/seal.py` SHA-256 校验保护，对下游自定义 `measure_*.py` 与 `check_*.py` 继续豁免。

---

## Batch 1：基础层单向化（Layer 0 `knobs.py` → Layer 1 `i18n.py` + 3 整包 JSON + `check_i18n.py`）

### 1.1 `zreflect/knobs.py` 极致深化（1,489L → ~230L，零本地 module import）
- **删除自指 C4 元警察与交叉耦合**：
  - 删除 `scan_surface_problems`、`readme_problems`、`declared_vs_read_problems`、`kind_vocabulary_problems`、`registry_vs_readme_problems`、`dead_default_problems`、`argparse_strip` 及依赖 `check_stale`/`check_retractions` 的 `_docs_scanned_by_gates`（套件完整性交由 `SEAL.json` + `ruff` 单源守卫）。
  - 将 `installed_langs`、`used_codes`、`a_pack_lang`、`pack_coverage_problems`、`pack_sync_problems` 迁出 `knobs.py` 归位至 `check_i18n.py` / `i18n.py`。
  - 去除对 `gate` 的导入，直接以 `root or os.environ.get("GATE_REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` 锚定被审计仓根目录，使 `knobs.py` 成为 **Layer 0（零本地 import）**。
- **修复旋钮默认值与全仓 15 处 `os.environ` 旁路**：
  - 将 `REGISTRY["REFLECT_DOCS"][1]` 默认值设为 `"STATE.md,AGENTS.md,README.md"`（将 `PRINCIPLES.md` 的管辖权唯一收敛到 `doc.accepts_principles()`；本仓根 `/knobs.json` 继续保留完整 6 文档声明）。
  - 在 `knobs.py` 的 `_cases()` 中新增一条轻量自测断言：扫描 `zreflect/*.py` 与 `reflect-hooks/*.py`（`knobs.py` 本身除外），禁止通过 `os.environ.get("REFLECT_...")` / `os.environ["REFLECT_..."]` 直接绕过 `knobs.get()` / `knobs.flag()` / `knobs._raw_knob()`。
  - 同步改造 `facts.py`（`REFLECT_MEASURE_MODULE`）、`i18n.py`（`REFLECT_I18N` / `REFLECT_LANG`）、`registry.py`（`REFLECT_PHASES`）、`runner.py`/`gate.py`（`REFLECT_REPLAY_TIMEOUT`）、`check_facts.py`（`REFLECT_NAKED_MIN`）、`check_history.py`（`REFLECT_HISTORY`）、`check_stale.py`（`REFLECT_STALE_DAYS` / `REFLECT_RETIRED`）、`check_ab.py`（`REFLECT_AB`）、`check_locks.py`（`REFLECT_LOCKS`）、`check_pins.py`（`REFLECT_PINS`）、`check_secrets.py`（`REFLECT_SECRETS`）、`check_instruments.py`（`REFLECT_INSTRUMENTS` / `REFLECT_INSTRUMENT_DAYS`）、`check_invariants.py`（`REFLECT_INVARIANTS`）、`check_world.py`（`REFLECT_WORLD` / `REFLECT_WORLD_LINE`）、`doctor.py`（`REFLECT_DOCTOR` / `REFLECT_DOCTOR_TIMEOUT`），统一经 `knobs` 解析，使 `knobs.json` 对全部 25 个旋钮一致生效。

### 1.2 `zreflect/machine.py` 并入 `zreflect/i18n.py`（443L 归零，消除四向循环）
- 将 `machine.py` 的 `ROWS`、`is_summary`、`scan`、`emit`、`emit_summary`、`clean`、`reject` 合并进 `i18n.py`，删除 `zreflect/machine.py` 与 `examples/machine/`（或将该能力示例合并至 `examples/i18n/`）。
- 更新 `gate.py`、`check_ab.py`、`check_facts_replay.py`、`check_i18n.py`、`check_locks.py`、`check_pins.py`、`doctor.py`、`harness.py`、`reflect-hooks/hook.py` 改为直接从 `i18n`（或 `gate.machine()`）使用，彻底打断 `gate ↔ machine ↔ i18n ↔ knobs` 循环导入。

### 1.3 合并 99 个语言包分片为 3 个单文件 + 校验归位 `check_i18n.py`
- 将 `zreflect/lang/{en,zh,de}/*.json`（共 99 个分片）各自合并、按键排序写入 3 个文件：
  - `zreflect/lang/en.json`
  - `zreflect/lang/zh.json`
  - `zreflect/lang/de.json`
  并删除 `zreflect/lang/en/`、`zreflect/lang/zh/`、`zreflect/lang/de/` 三个分片目录，精简 `i18n.load_pack()`（优先读取 `<lang>.json`，不再强依赖分片目录）。
- 将原本留在 `knobs.py` 的语言包完整性校验（`installed_langs`、`pack_sync_problems`、`pack_coverage_problems`、占位符及不可译机器行校验）统一收口至 `zreflect/check_i18n.py`。

---

## Batch 2：删除 `criteria.py` 与 AST 元警察，构建 Layer 2 `gate.py` + 精简 `registry.py`

### 2.1 删除 `zreflect/criteria.py`（1,552L），将有效职责迁入 `gate.py`
- 将 `criteria.exec_position_problems` / `prose_in_exec_problems` / `starts_with_interpreter`（针对用户配置 `world.json`、`pins.json`、`retractions.json`、`questions/*.md` 的命令形检查）精简后迁入 `zreflect/gate.py`。
- 删除 `zreflect/criteria.py`（其余 14 项 `dead_interface_problems`、`dependency_coverage_problems`、`path_rule_problems`、`off_reason_problems`、`encoding_surface_problems`、`subprocess_encoding_problems`、`fatal_exit_problems`、`suite_scope_problems`、`shell_surface_problems`、`trailing_newline_problems` 全部已被 `SEAL.json` + `ruff.toml` 覆盖，彻底退役）。

### 2.2 `runner.py` 与 Spec 公共入口并入 Layer 2 `zreflect/gate.py`
- 将 `zreflect/runner.py`（`run_cmd`、`quote`、`default_timeout`、`timeout_with_status`）直接并入 `gate.py`，使用标准库 `shlex` 与跨平台命令改写，删除 `zreflect/runner.py`。
- 在 `gate.py` 新增两项公共基础设施：
  - `sha256_file(path)`：供 `seal.py` 与 `check_locks.py` 复用；
  - `run_spec_gate(argv, knob_name, prefix, judge_fn, ok_key="ok")`：封装 Spec 定位（`--spec > knobs.get(knob_name) > default`）、缺失时按 `explicit` 分别返回 `fatal` 或 `off`、`load_spec` 损坏报错、`skips` 输出与 `finish()` 汇总。
- 删去 `gate.never_falsifiable()`（123L lambda AST 解析器），为 `gate.py` 增加轻量独立 `--selftest`，删去 `registry.py` 中代管的 `_cases_gate_hosted` 与源码注释字符串匹配自测（`_streams_documented`、`_gate_desc_states_selftest`）。

### 2.3 精简 `zreflect/registry.py`（1,168L → ~360L） & `zreflect/seal.py`
- `registry.problems()` 只核验：声明合法性（`phases_problems`、`missing_declaration`、`phase_problems`、`empty_gate_problems`、`selftest_roster_problems`、`undeclared_module_problems`）、用户配置校验（`knobs.config_problems()`）以及核心封签校验（`seal.verify_problems()`），耗时从 ~2.2s 降至 <0.1s。
- 更新 `zreflect/seal.py` 以适配 3 个单文件语言包（`zreflect/lang/*.json`），移除对已删除 `criteria.py` 的依赖（如 shell 白名单在 100% 纯 Python 后直接删除）。

---

## Batch 3：坍缩台账集群（`facts.py` 吸收 `ledger.py` + `living.py`）、删除 `echoes.py`、瘦身 `doc.py` 与合并 Hook

### 3.1 合并 `ledger.py` (515L) + `living.py` (146L) → `zreflect/facts.py`
- 删除 `zreflect/ledger.py` 与 `zreflect/living.py`，将全部台账读写/写守卫（`load`, `load_or_fatal`, `facts_of`, `fact`, `decide`）、机器块渲染/解析（`render_block`, `body_of`, `prose_of`, `block_homes`, `doc_block_problems`）及活文档划分（`HIST_MARK`, `DATED_RECORD`, `CITE_RE`, `section_is_living`, `living_lines`）统一归入 **Layer 4 `zreflect/facts.py`**。
- 反转并消解 `facts ↔ check_facts` 循环依赖：由 `check_facts.py`（以及 `check_stale`、`check_retractions`、`check_instruments`、`check_facts_replay`）单向导入 `facts`。
- 优化 `cmd_render_doc()` 与 `cmd_check()`：循环外仅计算一次 `block_homes(ledger)` 传入，不重复遍历名录。
- 用基于 `tempfile.TemporaryDirectory` 的进程内直接测试替代 `facts.py` 里 6 处调用 `_copy_suite_into()` 复制整仓并起全量 commit 子进程的 460 行重型自测，将 `facts.py --selftest` 从 ~82s 压至 <0.5s。

### 3.2 删除 `zreflect/echoes.py` (214L) 与 `examples/echoes/`
- 删除 `zreflect/echoes.py`、`examples/echoes/` 及 `check_facts.py` 中的 `_echo_problems()` 调用：三载体边界由 `STATE.md`/`PRINCIPLES.md` 禁止块外手写散文及各载体各自的命令行契约（值命令 / rc=0 判据 / `Settling` 双态命令）刚性保障，不再做跨载体文本模糊比对。

### 3.3 瘦身 `zreflect/doc.py`（774L → ~180L）与 `zreflect/check_facts_replay.py`
- 从 `doc.py` 删除 `dangling_references()`（150L 动态全仓 import + AST 爬行器）、`round_narrative_problems()` 与 `_cmd_shape_problems()` 及其 120 行自测脚手架。
- 清理 `doc.RULES` 中与 `registry.py --run commit` 重复执行 8 道 `check_*.py` 的规则项以及每次 commit 耗费 6.6s 重跑 39 个单测的 `registry.py --selftest`（`falsifiable` 改由声明检查 + `harness.py` 守卫），同步移除指向已废除模块（`criteria`、`echoes`、`machine`）的过时规则。
- 在 `check_facts_replay.py` 中对相同 `cmd` 去重执行，避免同一条命令（如 `--verify-seal`）在同一提交内被重复执行多次。

### 3.4 合并 `reflect-hooks/install.py` → `reflect-hooks/hook.py` 并实现 100% 纯 Python
- 将 `reflect-hooks/install.py` 的 `--chain` / `--uninstall` / 接线提示逻辑合并入 `reflect-hooks/hook.py`（共用 `HERE`、`TOOL_REPO`、`_sh`、`PHASE_OF`），删除 `reflect-hooks/install.py`。
- 删除无人调用的 `reflect-hooks/quality-record.sh`、`examples/quality_record/`、`.shellcheckrc`、`gitroll-dispositions.json`、`zreflect/world.json.example`、`zreflect/doctor.json.example`；更新 `examples/hooks/` 与 `.github/workflows/gates.yml`（移除 `shellcheck` 步骤，套件实现 100% 纯 Python）。

---

## Batch 4：全仓 8 道 Spec 闸门去重、拍平 `_cases_*` 碎片、修复 4 个实操 Bug 与全量收口

### 4.1 8 道 Spec 闸门收口至 `gate.run_spec_gate()`
- 重构 `check_ab.py`、`check_locks.py`、`check_pins.py`、`check_invariants.py`、`check_instruments.py`、`check_world.py`、`check_secrets.py`、`doctor.py`：删掉各自重复的 `resolve_spec` 透传壳、JSON 加载与缺失判断样板，统一调用 `gate.run_spec_gate()`（及 `knobs` 读取）。

### 4.2 解除 `check_explain.py` 的反激励与清理全仓历史长文 / `_cases_*` 金字塔
- 更新 `zreflect/check_explain.py`：对名如 `_cases` / `_cases_*` 的自测夹具函数豁免注释预算统计，消除为了凑每函数 300 字符注释预算而被迫拆分的 5~7 层 `_cases_a(fx)` 金字塔与 dict 传递样板。
- 拍平各 `check_*.py`、`harness.py`、`examples.py`、`next.py` 中碎裂的 `_cases_*` 为单张平铺 `_cases()` 表；剥离源码头部及行间堆砌的"第 N 轮 / issue #M"长篇历史叙事（保留在 `HISTORY.md`），源码注释仅保留简洁的接口契约与关键不变量说明。
- `zreflect/harness.py` 改由进程内直接调用 `registry.gates()`、`registry.plugins()`、`registry.selftest_modules()`、`registry.red_need()`，消除无谓的 5 次 `registry.py` 子进程拉起。

### 4.3 修复 Dogfood 实操发现的 4 个真实体验与正确性 Bug
1. **`REFLECT_NO_PRINCIPLES=1` 协同**：因 Batch 1 已将 `PRINCIPLES.md` 移出 `REGISTRY["REFLECT_DOCS"]` 默认列表，`check_facts._docs_to_scan()` 与 `facts._doc_names()` 统一通过 `doc.accepts_principles()` 追加 `PRINCIPLES.md`，下游退出原则不再报错。
2. **`questions/01-example.md` 与 `next.py` 空分支**：`facts.py --init` 生成的 `questions/01-example.md` 默认写入 `**Status:** resolved`（与可执行示例 `python3 -c "raise SystemExit(0)"`），既保持目录非空又不在 `next.py` 中持续误报；`next.py` 对 `git rev-parse --verify HEAD` 失败的 unborn 分支输出正常提示而非"git unavailable"。
3. **`facts.py --accept` 类型与 `check_facts.py` 校验缺口**：
   - `facts.py cmd_accept()` 自动将合法十进制整数字符串转为 `int` 存入 `FACTS.json`，使手动注册的数字可被裸数字黑白名单校验；
   - `check_facts.py` 对 `REFLECT_DOCS` 中的全部文档统一运行 `_cite_problems` 检查悬空 `[[key]]` 引用（并在 `_has_provenance` 中核验同行数字与所引 `[[key]]` 值的一致性）；
   - 修复 `facts.py` 自测 `★ facts.check_doc_no_markers` 传递 `"STATE.md"` 而非未登记的 `"doc.md"`，确保真正测中 `facts.markers_missing_check`；
   - 在 `facts.py --init` 生成的 `STATE.md` 骨架顶部引用块明确提示可在引言 `>` 区嵌入 `[[key]]` 引用。

### 4.4 语言包、`FACTS.json`、`STATE.md`、`PRINCIPLES.md` 与文档同步
- 更新合并后的 `zreflect/lang/{en,zh,de}.json`，剔除已删模块的无用键并确保与所有残余 `M(...)` 调用 100% 精确对齐。
- 更新 `AGENTS.md`、`README.md`、`README.zh.md`、`README.de.md`、`examples/README.md`、`skills/einfacht/SKILL.md`、`secrets.json`、`.gitignore` 与 `.github/workflows/gates.yml`。
- 依次执行 `python3 zreflect/registry.py --reseal=ALL`、`python3 zreflect/facts.py --allow-drop --accept-changes`、`python3 zreflect/facts.py --render-doc`，并跑通 `ruff check .`、`facts.py --check`、`check_explain.py`、`registry.py --verify-seal`、`registry.py --run commit`、`examples.py --all` 以及 null / `en` / `zh` / `de` 四环境下的 `harness.py`。
- 最后将本悬案标记为 `**Status:** resolved`。
