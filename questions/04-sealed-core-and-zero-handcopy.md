# 04: 共用核心硬哈希自锁、穿透式自证与全仓零手抄收口

**What to build:** 为共用核心建立双层硬哈希封条（锁死裁判标尺与核心全文、放开各仓自主测量模块）并嵌入台账三重互锁；焊死自证可证伪性与依赖覆盖的 AST 逃逸口；将注释纪律改造为「注释总量（docstring + `#` 注释）由 AST 分支复杂度买单」；清剿残余的手抄默认值、平行解析器与手写名录，并通过 Git 钩子自动完成全量机器块渲染与对账。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/registry.py --verify-seal && python3 zreflect/registry.py --run commit && python3 zreflect/harness.py —— rc=0 ⇒ 已全部完成：新增 `zreflect/seal.py` 与 `zreflect/SEAL.json`（双层 SHA-256 封条，放开 `measure_*.py` / `Einfacht.env` / 自定义相位闸门）；加深 `never_falsifiable` 辅助函数穿透、多 lambda 检查与 `dependency_coverage`/`dead_interface` AST 范围；守卫 `cmd`/`calibrate` 并合并三块渲染与校对；统一执行位、`knobs.get()` 与动态引用发现；将 `check_explain.py` 改为 `300 + 120*branches + 60*args` 复杂度预算并默认开启。

## Problem Statement

站在套件维护者与下游接入仓库拥有者的视角，当前系统在「自证未经篡改/未放水」与「零手抄单产地」两个维度存在六处结构性裂缝：

1. **共用核心缺乏防篡改硬哈希封条，下游或无人值守会话可就地改弱裁判**：各仓库共用的核心代码与语言包拷入下游后，没有任何密码学指纹自证其未被修改。Agent 遇到闸门判红时，若直接改弱核心闸门实现及其自测用例，本地自测与提交闸门依然全绿。
2. **自证可证伪性（Falsifiability）与覆盖率检查存在 AST 逃逸口**：
   - 将自测用例委托给同模块辅助函数（`lambda: _helper()`）时，可证伪性检查只打 `delegated` 标记并放行，从不深入辅助函数体检查是否恒返真值；
   - 同一行出现多个 `lambda` 时，定位函数因候选数大于 1 直接返回 `None` 免检；
   - 平台函数断言覆盖检查遍历了含 `_cases` 的整份文件 AST，导致生产代码里的调用被误判为“已在自测中断言”；死接口检查把模块自身的注释与自测当成外部消费者，漏掉了零外部调用的孤儿接口。
3. **台账守卫与机器块校验分裂，且原则在两份文档中重复落盘**：
   - 台账写盘守卫只比对 `value`，忽略 `cmd` 与 `calibrate` 的改动——直接把台账里的复跑命令改成恒真输出即可静默绕过复跑闸门；
   - 提交阶段的事实闸门只校验状态机器块，不校验闸门名录块与原则机器块，且钩子在 `commit` 阶段未自动渲染原则文档；
   - 状态文档的机器块重复渲染了全部原则条目，与原则文档形成跨载体冗余。
4. **执行位（Execution Position）判据分裂成三套浅实现**：原则表中的执行位规则未接入全载体收集器；问题单的结算字段存在两套不相容解析器；翻案台账的证据字段只查子串或首词，放过了大量“以解释器开头、后跟中文散文”的不可执行条目。
5. **旋钮默认值与读取声明仍是单向或手抄状态**：二十余处代码绕过旋钮登记表硬编码默认文件名；旋钮声明对账只查“声明未读”，不查“读而未声明”，导致部分闸门漏报消费旋钮，连带使环境提示与改名自证失准。
6. **注释纪律靠判定词猫鼠游戏与固定字数阈值，被“剪字数、拆 1 行透传辅助函数、转入 `#` 注释”绕过**：
   - 固定字符上限与函数复杂度脱钩，拆分零分支的 1 行透传函数即可凭空成倍获取注释额度；
   - 只扫描 docstring 而不统计函数体内 `#` 注释，导致长篇历史叙述转移到 `#` 注释中完全逃逸；
   - 靠自然语言时态词表（`TEMPORAL`）猜测历史叙述，陷入换词绕过的猫鼠游戏；且原则表在注释旋钮未设置时将 `off` 状态洗白为通过。

## Solution

将整套系统沿着「共用核心刚性自锁 + 各仓测量自主 + 钩子全自动渲染 + 复杂度决定注释额度」重新加深（Deepening）：

1. **双层硬哈希封条与三重互锁（Two-Tier Hard Hash Seal & Triple Interlock）**：
   - 区分**共用核心非可修改区**（核心模块、闸门、语言包、钩子脚本、静态检查配置）与**各仓自主可修改区**（`measure_*` 测量模块、`Einfacht.env` 钩子载体、自定义阶段扩展闸门、台账与文档载体）。
   - 对非可修改区建立双层硬哈希封条：**Tier 1（裁判标尺哈希）** 单独锁定每个文件的自测函数区间、声明区间、原则表与静态规则配置；**Tier 2（核心全文哈希）** 锁定全部核心文件字节并汇总为单根哈希（`tree_sha256`）。
   - 将封条校验同时接入单模块 `--selftest` 入口、名录自洽检查、原则表 `core_sealed` 条目以及台账 `core_seal` 事实，形成“改代码必破封条、伪造封条必破台账复跑、重写台账必被写盘守卫拦截”的三重互锁。
2. **穿透式 AST 自证与真实测试面覆盖**：
   - 可证伪性检查穿透同模块辅助函数 `FunctionDef`，拦截恒真返回与短路表达式；同行多 `lambda` 逐一全扫；
   - 断言覆盖率严格限制在 `_cases*` / `_fixture*` 函数子树内；死接口检查仅认跨模块引用或本模块非自测生产引用。
3. **台账命令守卫、原则去重渲染与 Git 钩子全自动化**：
   - 写盘守卫将 `(value, cmd, calibrate, calibrate_expect)` 一并纳入变更拦截；
   - 提交阶段事实闸门复用统一的机器块归属表，一次校验全部机器块（状态、闸门、原则）并核对台账中的原则命令与原则表逐字节一致；
   - 状态机器块只渲染状态事实，不再重复列出原则条目；`pre-commit` 钩子自动重渲染全部机器块文档并暂存，删除手工 `--accept-principles` 子命令。
4. **单一执行位 Seam、单一旋钮读取 Seam 与全自动引用发现**：
   - 四个执行位载体统一走同一套命令语法校验与问题字段解析器，清理翻案台账中的伪命令散文；
   - 旋钮模块提供统一读取出口并由 AST 规则禁绝外部内联默认字面量，`declared_vs_read` 升级为双向相等对账；
   - 文档符号引用检查改为从核心目录动态发现全部模块，并将 Python docstring 纳入悬空引用扫描。
5. **注释总量与 AST 复杂度挂钩（废除判定词表）**：
   - 删除时态词表、`--temporal` 与 `--classify` 分类器；
   - 函数的解释总量定义为 `docstring 字符数 + 函数区间内非指令 # 注释字符数`，允许额度由函数的 **AST 分支复杂度与接口参数数** 线性决定。由于分支数在函数拆分下守恒，拆 1 行零分支透传函数不再产生额外注释额度，转入 `#` 注释也无法逃逸。

## User Stories

1. As a **downstream repo owner**, I want my copy of the shared core to verify its own hard SHA-256 seal on every commit and selftest, so that an agent working in my repo cannot silence a failing gate by editing the gate or its selftest cases.
2. As a **downstream repo owner**, I want my custom measurement module (`measure_*`), hook carrier (`Einfacht.env`), and custom-phase gates (`REFLECT_PHASES`) excluded from the shared core seal, so that I can freely define what my repo measures without breaking core integrity checks.
3. As a **core maintainer**, I want Tier 1 yardstick hashes (`_cases*`, `GATE`/`MODULE` declarations, `RULES`, static lint config) tracked separately from Tier 2 implementation hashes, so that refactoring implementation code immediately fails if I accidentally touch a test case or rule threshold.
4. As a **core maintainer**, I want yardstick resealing to enforce a monotonicity guard on total case count and red-case (`★`) count, so that no one can reseal a module after deleting selftest assertions without an explicit drop flag.
5. As a **core maintainer**, I want the core seal's Merkle root (`tree_sha256`) stored as a replayed ledger fact (`core_seal`) guarded by the ledger write guard, so that forging the seal file itself is caught by ledger replay and blocked by the write guard.
6. As a **core maintainer**, I want cross-platform line-ending normalization (`\r\n` to `\n`) applied before hashing text files in the core seal, so that Linux and Windows CI runners compute the exact same 64-character SHA-256.
7. As a **suite auditor**, I want `never_falsifiable` to resolve same-module helper functions called by a selftest lambda and inspect their AST return paths, so that `lambda: _helper()` where `_helper` returns a constant `True` or short-circuit is rejected as unfalsifiable.
8. As a **suite auditor**, I want `never_falsifiable` to inspect every lambda node on a source line when multiple lambdas share a line number, so that nesting two lambdas on one line no longer bypasses falsifiability inspection.
9. As a **suite auditor**, I want platform-function assertion coverage (`dependency_coverage_problems`) to walk only `_cases*` and `_fixture*` AST subtrees rather than the whole file, so that calling a platform function in production `run()` no longer counts as testing it.
10. As a **suite auditor**, I want dead-interface detection (`dead_interface_problems`) to ignore occurrences inside comments, docstrings, and a module's own `_cases*` functions, so that public platform functions with zero production callers are immediately flagged.
11. As a **repo owner**, I want the ledger write guard (`decide`) to refuse unaccepted changes to `cmd`, `calibrate`, or `calibrate_expect` alongside `value`, so that measurement or principle commands in the ledger cannot be silently swapped for `echo` stubs.
12. As a **repo owner**, I want the commit-phase facts gate to verify all three machine blocks (`AUTO:FACTS`, `AUTO:GATES`, `AUTO:RULES`) and reconcile principle entries in the ledger byte-for-byte against the principles registry, so that stale blocks or tampered principle commands are caught on every commit.
13. As a **repo reader**, I want `STATE.md`'s `AUTO:FACTS` block to render only state/numeric facts while `PRINCIPLES.md`'s `AUTO:RULES` block renders principles, so that the 21 principles are not duplicated across both documents.
14. As a **developer**, I want `facts.py --render-doc` (with no file argument) and the `pre-commit` hook to automatically render and `git add` all machine-block documents (`STATE.md` and `PRINCIPLES.md`), so that I never have to run multiple manual render commands or `--accept-principles`.
15. As a **suite auditor**, I want the `exec_position_is_a_command` principle wired to the unified collector across all four carriers (world stamps, pins, question settlers, retraction evidence), so that no execution position escapes command validation.
16. As a **suite auditor**, I want question `Settling:` parsing to have a single origin that honours `REFLECT_QUESTIONS`, continuation lines, and `does not exist / first deliverable` declarations, so that roster criteria and the question gate never disagree.
17. As a **suite auditor**, I want execution-position validation to reject commands with trailing unquoted prose commentary, and all existing retraction evidence entries cleaned up to pure runnable commands, so that every retraction refutation is genuinely replayable.
18. As a **gate author**, I want a single knob-reading interface on the knob registry module and an AST rule forbidding inline fallback literals outside that module, so that default filenames and numbers are never hand-copied in gate code.
19. As a **gate author**, I want `declared_vs_read_problems` to check both directions (`declared == read` across production functions and knob helpers), so that gates cannot read a knob without declaring it in `GATE = meta(..., knobs=...)`.
20. As a **suite maintainer**, I want `dangling_references` to dynamically discover all declared modules in the suite and scan both markdown docs and Python docstrings, so that stale symbol references (like nonexistent helper names in docstrings) are caught automatically without maintaining a hardcoded 14-module tuple.
21. As a **suite maintainer**, I want the path-rule check to catch any self-computation of `dirname(abspath(__file__))` inside function bodies (including local variable assignments, not just `return` statements), so that `gate.zdir()` remains the true single origin.
22. As a **code reviewer**, I want `check_explain` to measure total explanation volume (docstring characters + in-function `#` comment characters) against an AST complexity budget (`branches` and `args`) instead of a flat 500-character cliff or a `TEMPORAL` word list, so that authors cannot game the gate by shaving docstrings to 499 characters, moving prose into `#` comments, or extracting 1-line pass-through helpers.
23. As a **repo owner**, I want `REFLECT_COMMENTS=mismatch` enabled by default in this repo and the `off`-laundering wrapper in the principles table removed, so that comment discipline is actively enforced on every commit.

## Implementation Decisions

### 1. Shared Core Hard-Hash Seal Module & Seam
- **Single Seal Carrier (`SEAL.json`)**: Lives inside the suite directory and records deterministic SHA-256 digests (computed over UTF-8 bytes with `\r\n` normalized to `\n`):
  ```json
  {
    "schema": 1,
    "tree_sha256": "<64-char merkle root>",
    "files": {
      "zreflect/gate.py": {
        "file_sha256": "<64-char sha256>",
        "yardstick_sha256": "<64-char sha256 of _cases* + _fixture* + GATE/MODULE + RULES spans>",
        "cases": 18,
        "red_cases": 9
      }
    }
  }
  ```
- **Boundary Between Non-Modifiable Core and Consumer Surface**:
  - **Included in Seal**: All suite `.py` files declaring `GATE` or `MODULE` under `zreflect/` and `reflect-hooks/`, all language pack shards (`zreflect/lang/*/*.json`), all whitelisted shell scripts (`ALLOWED_SHELL`), `gates-selftest.sh`, and `ruff.toml`.
  - **Excluded from Seal**: Consumer measurement modules (`zreflect/measure_*.py`), the hook carrier (`reflect-hooks/Einfacht.env`), `zreflect/SEAL.json` itself, and any consumer gate whose declared `runs_at` phase is a custom phase added via `REFLECT_PHASES`.
- **Reseal Ceremony & Monotonicity**:
  - Verification runs via `registry.py --verify-seal` (printing `tree_sha256` on `rc=0`, problem rows on `rc=1`), inside `gate.selftest()` when `SEAL.json` is present, and inside `registry.problems()`.
  - Updating the seal requires explicit file nomination: `--reseal=<path,...>` updates `file_sha256` only and refuses if `yardstick_sha256` changed; `--reseal-yardstick=<path,...>` updates both but refuses if `cases` or `red_cases` decreased unless `--allow-case-drop` is also passed.

### 2. Deepening the AST Falsifiability & Coverage Seam (`gate` & `criteria`)
- **Helper-Penetrating `never_falsifiable`**:
  - Remove the `len(nodes) > 1` bailout in `_falsifiability_located`: scan all `Lambda` nodes on the target line and report if any candidate is unfalsifiable.
  - When a lambda body is a single non-builtin `ast.Call` targeting a same-module function name, resolve the target `ast.FunctionDef` in the cached module AST. Reject the case as unfalsifiable (`rc=1`, not a passing `note | delegated`) if the helper cannot be resolved, contains any short-circuit / self-comparison, or has all `ast.Return` nodes returning constant truthy values without a comparison or call.
- **Scoped `_asserted_names` and `_consumed`**:
  - `_asserted_names` walks only `ast.FunctionDef` nodes whose name starts with `_cases` or `_fixture`.
  - `dead_interface_problems` uses AST `Load` analysis: a public function in a platform module is consumed only if referenced outside its own module or referenced by non-`_cases*` production code / module-level dispatch tables within its own module.

### 3. Ledger Guard, Machine-Block Unification & Hook Automation (`guard`, `facts`, `check_facts`, `render`, `reflect-hooks/gate`)
- **Command & Calibration Guard**: `ledger.changed_keys` and `guard.decide` compare `(value, cmd, calibrate, calibrate_expect)` for each key instead of `value` alone.
- **Unified Block Homes Seam**: Extract `block_homes(ledger)` so both `facts.py --check` and `check_facts.py` verify all active machine blocks (`AUTO:FACTS` and `AUTO:GATES` in the state doc, `AUTO:RULES` in `PRINCIPLES.md`), plus byte-for-byte agreement between `doc.facts_of_rules()` and `principle.*` entries in `FACTS.json`.
- **De-duplicating Principles from `STATE.md`**: `render.render_block(ledger)` filters out entries where `kind == "principle"`, keeping `STATE.md` strictly about measured repo state while `PRINCIPLES.md` renders the rules table.
- **Hook & CLI Automation**:
  - `facts.py --render-doc` (with no positional doc argument) renders all documents returned by `_doc_names()` (`STATE.md` and `PRINCIPLES.md`), matching `facts.py --check`.
  - `reflect-hooks/gate.py` in `commit` phase invokes `facts.py --render-doc`, checks its return code, and `git add`s all rendered machine-block documents.
  - Remove the redundant `cmd_accept_principles` (`--accept-principles`) handler; `facts.py` measurement automatically syncs `doc.facts_of_rules()` into `FACTS.json` when `doc.accepts_principles()` is true.

### 4. Single Execution-Position, Knob Read, and Reference Discovery Seams (`criteria`, `knobs`, `doc`, `check_questions`, `check_retractions`)
- **Execution Positions**:
  - `doc.RULES["exec_position_is_a_command"]` invokes `criteria.all_exec_position_problems()`.
  - `criteria._settling_problems` delegates question collection and `Settling` extraction to `check_questions.collect()` and `check_questions.field()` (honouring `NONE_LIKE` first-deliverable declarations).
  - `check_retractions._evidence_problems` delegates to `criteria.prose_in_exec_problems()`.
  - `criteria.starts_with_interpreter` validates the command segment (before `----` / `——` outcome separators) to reject trailing unquoted prose commentary; all 14 prose-suffixed `evidence` strings in `retractions.json` are cleaned to pure runnable commands.
- **Single Knob Read & Bidirectional Declaration Check**:
  - Add `knobs.get(name)` and `knobs.repo_path(name, root=None)` as the single read seam; replace inline default literals across gates.
  - Extend `knobs.dead_default_problems` to report any `os.environ.get("REFLECT_...", "<non-empty literal>")` outside `knobs.py`.
  - Upgrade `knobs.declared_vs_read_problems` to enforce `declared == read` over each gate's production AST (including calls to `knobs.*` helper functions).
- **Discovered Symbol References & Path Rule**:
  - Replace hardcoded `REFERENCE_MODULES` and `REFERENCE_DOCS` in `doc.py` with dynamic discovery over `gate.zdir()` and `knobs` document lists, plus all suite `.py` docstrings.
  - Replace the duplicate round-narrative regex in `doc.py` with a single function called by both the rule command and the selftest.
  - Widen `criteria._returns_self_computed_dir` to inspect all AST nodes inside function bodies (catching local variable assignments like `base = os.path.dirname(os.path.abspath(__file__))`), and switch `doc.py` to `gate.zdir()` / `gate.tool_repo()`.

### 5. Complexity-Proportional Comment Discipline (`check_explain`)
- **Retire Word-List Heuristics**: Delete `TEMPORAL`, `classify()`, `classify_tree()`, `temporal_reports()`, `--classify`, and `--temporal`.
- **Unified Explanation Volume & Complexity Budget**:
  - For every function AST node in `zreflect/` and `reflect-hooks/`:
    $$\text{explain\_chars}(f) = \text{len}(\text{docstring}(f)) + \sum_{\text{comment } c \in \text{span}(f)} \text{len}(c)$$
    (excluding `# noqa` / `# type: ignore` / shebang pragmas).
  - Branching complexity $\text{branches}(f)$ counts `If`, `For`, `AsyncFor`, `While`, `ExceptHandler`, `With`, `AsyncWith`, `BoolOp`, `IfExp`, `Raise`, and `comprehension.ifs` inside $f$'s body (excluding nested function defs, which are judged on their own).
  - Under `mismatch` mode, a function reports `comments.explain_exceeds_complexity` when:
    $$\text{explain\_chars}(f) > B_0 + k_b \cdot \text{branches}(f) + k_a \cdot \text{args}(f)$$
    Because $\text{branches}(f)$ is additive under function extraction, splitting a function into 0-branch pass-through helpers yields zero additional branch budget.
  - Enable `REFLECT_COMMENTS=mismatch` by default and make `Rule("comments_earn_their_place")` invoke `python3 zreflect/check_explain.py` directly without laundering `off`.
  - Supersede and close `questions/02-comment-triage.md` and `questions/03-strict-docstrings.md` once `check_explain.py` passes under the complexity budget.

## Testing Decisions

- **What makes a good test**: Test external behavior and verdicts at each module's public interface (`problems()`, `decide()`, `never_falsifiable()`, `verify_seal()`, CLI exit codes `0 / 1 / 2` and machine rows), never internal private helper names. Every new criterion must have a `★` red-path case (planted violation goes red), a clean positive-control case, and a zero-value guard case.
- **Primary Testing Seams (Highest Possible Seams)**:
  1. `registry.problems()` & `registry.py --verify-seal`: single seam for roster reconciliation, bidirectional knob declarations, path-rule assignment detection, dead-interface AST detection, assertion coverage in `_cases*`, and two-tier hard-hash seal verification (planted 1-byte edit in code, planted 1-byte edit in `_cases`, planted case-count drop).
  2. `gate.never_falsifiable()` & `gate.selftest()`: seam for helper-penetrating AST falsifiability (planted `lambda: _always_true_helper()` and planted dual-lambda line must both fail with `gate.case_unfalsifiable`).
  3. `check_facts.problems()` & `guard.decide()`: seam for three-block verification (`AUTO:FACTS`, `AUTO:GATES`, `AUTO:RULES`), `doc.RULES` ↔ `FACTS.json` command reconciliation, and refusal of unaccepted `cmd`/`calibrate` edits.
  4. `criteria.all_exec_position_problems()`: seam across all four carriers (`world.json`, `pins.json`, `questions/*.md`, `retractions.json`) rejecting prose-suffixed commands.
  5. `check_explain.problems()`: seam verifying that both oversized docstrings and oversized in-function `#` comments on low-complexity functions report `comments.explain_exceeds_complexity`, while high-complexity functions with proportional contract comments pass.
- **Prior Art in Codebase**: Injected `sources={...}` / `files={...}` dictionary fixtures in `criteria._cases_*`, `knobs._cases_*`, `guard._cases_*`, and temporary repo fixtures in `harness.run_configurable` and `examples.py`.

## Out of Scope

- Changing how downstream consumer repos implement their own `measure()` logic or what project metrics they choose to collect.
- Network verification of upstream URLs in `check_locks.py` or container execution changes in `check_pins.py`.
- Adding any host-specific editor hook configuration (the `host_agnostic` rule stands).
- Adding new natural-language translation packs beyond `en`, `zh`, and `de`.

## Further Notes

- Execution order should proceed in 5 self-contained commits/batches so that `SEAL.json` is generated and locked last (or updated explicitly at each batch boundary via `--reseal`), ending with `registry.py --run commit`, `examples.py --all`, and `harness.py` (under null pack + `en` / `zh` / `de`) all green at `failed=0, fatal=0`.
