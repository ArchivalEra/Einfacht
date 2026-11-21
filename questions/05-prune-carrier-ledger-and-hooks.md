# 05: 移除 `Einfacht.env` 壳层载体、合并台账三模块、收口单入口钩子与单层核心封条

**What to build:** 删除 `Einfacht.env` / `einfacht-env.sh` / `check_envfile.py` / `env_hint` 壳层配置家族，将单仓旋钮覆盖收敛至 `knobs.py` 直读的可选 `knobs.json`；将 `guard.py` 与 `render.py` 并入 `ledger.py`，停止向 `FACTS.json` 镜像 `principle.*` 并由 `check_facts_replay.py` 直接复跑 `doc.RULES`；删除 `--legacy` 钩子模式与 `pre-commit`/`pre-push` shell 垫片，将 `reflect-hooks/gate.py` 重命名为 `reflect-hooks/hook.py` 并修复多提交 `pre-push` 与部分暂存 `pre-commit` 失步；将 `seal.py` 收缩为单层全文哈希（放行下游自定义闸门）、收缩 `gate.never_falsifiable` 为直接恒真拦截、删除 `gates-selftest.sh` 并修复 Windows 路径分隔符缺陷。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 -c "import json,os,sys; gone=('reflect-local/Einfacht.env','reflect-local/Einfacht.env.example','reflect-local/einfacht-env.sh','zreflect/check_envfile.py','zreflect/guard.py','zreflect/render.py','reflect-local/pre-commit','reflect-local/pre-push','reflect-local/gate.py','gates-selftest.sh'); facts=json.load(open('FACTS.json',encoding='utf-8')).get('facts',{}); sys.exit(0 if (not any(os.path.exists(p) for p in gone) and os.path.isfile('reflect-local/hook.py') and not any(k.startswith('principle.') for k in facts)) else 1)" && python3 zreflect/registry.py --verify-seal && python3 zreflect/registry.py --run commit && python3 zreflect/harness.py —— rc=0 ⇒ 壳层载体、冗余台账模块、旧钩子垫片与 `gates-selftest.sh` 已移除，`hook.py` 与单层封条就位且全量闸门与自证通过；rc≠0 ⇒ 仍有待删文件/`principle.*` 残留或闸门未绿

## 锁定边界（不可改动）

- **保留 `check_*` 闸门语义与三分载体**：`PRINCIPLES.md`（规则表）、`STATE.md`（测量事实）、`questions/`（悬案结算）职责不变；可插拔闸门继续通过旋钮启停。
- **保留零语言核心输出（`zreflect/i18n.py` + `zreflect/check_i18n.py`）**：未激活语言包时输出 `code(k=v)` 机器行供宿主程序/办公软件无头消费；`en` / `zh` / `de` 语言包保持可选覆写。

---

## Batch 1：移除 `Einfacht.env` 家族，将单仓配置收口至 `knobs.py`

### 1.1 删除清单
- 文件：
  - `reflect-hooks/Einfacht.env`
  - `reflect-hooks/Einfacht.env.example`
  - `reflect-hooks/einfacht-env.sh`
  - `zreflect/check_envfile.py`
  - `examples/check_envfile/example.json`、`examples/check_envfile/broken.env`（及目录 `examples/check_envfile/`）
  - `zreflect/lang/en/envfile.json`、`zreflect/lang/zh/envfile.json`、`zreflect/lang/de/envfile.json`
  - `zreflect/lang/en/hookenv.json`、`zreflect/lang/zh/hookenv.json`、`zreflect/lang/de/hookenv.json`
- 符号与分支：
  - `zreflect/knobs.py:105-108`：删除 `REGISTRY` 中的 `"REFLECT_ENV_FILE"` 与 `"REFLECT_ENV_HINT"`，同步删除 `zreflect/lang/{en,zh,de}/knobs.json` 中的 `knobs.sem.reflect_env_file` 与 `knobs.sem.reflect_env_hint`。
  - `zreflect/gate.py:260-336,345-351`：删除 `env_carrier()`、`env_hint()` 及 `finish()` 中的 `env_hint` 打印逻辑；删除 `zreflect/lang/{en,zh,de}/gate.json` 中的 `gate.env_hint`。
  - `zreflect/guard.py:73-96,276-291`（并入 `ledger.py` 前）：删除 `carrier_exists` 参数、`guard.write_target_env_carrier` 与 `guard.write_target_env_carrier_after`（含 `zreflect/lang/{en,zh,de}/guard.json` 对应键）。
  - `zreflect/registry.py:490-515,654-667,1170-1242`：从 `plugins()` 移除 `reflect-hooks/einfacht-env.sh`；删除 `_ADVISORY_CODES`、`_env_hint_case()` 与 `_cases_hint()`。
  - `zreflect/criteria.py:66,80-108,827-860,1160-1165,1487-1495`：从 `ALLOWED_SHELL` 移除 `"reflect-hooks/einfacht-env.sh"`；`_REASON_BASES` 仅保留 `(gate.GATE_REPO,)`；删除 `reason_bases_agree()`、`registry.off_reason_stale_in_hooks_dir` 与 `registry.reason_bases_match_env_plugin`（含 `zreflect/lang/{en,zh,de}/registry.json` 中的 `registry.reason_bases_disagree`）。
  - `zreflect/facts.py:827-855,1042-1043,1158,1289-1299,1311-1333`：删除 `_init_env_carrier()`、`_env_from_envfile()`、`_host_env_carrier_not_copied()`；删除 `zreflect/lang/{en,zh,de}/facts.json` 中的 `facts.init_env_exists_in_hooks`。
  - `zreflect/examples.py:157-194`：删除 `_carrier_exports()`。
  - `reflect-hooks/gate.py:68-109,223`：删除 `_plugin_exports()` 与 `_load_env_plugin()`。

### 1.2 修改与新增
- `zreflect/knobs.py`：
  - 将 `REGISTRY["REFLECT_DOCS"][1]`（`knobs.py:83`）改为 `"STATE.md,PRINCIPLES.md,AGENTS.md,README.md"`；将 `REGISTRY["REFLECT_READMES"][1]`（`knobs.py:97`）改为 `"README.md"`。`facts.py --init` 生成的单 README 仓库无需任何额外配置文件即可通过全部默认闸门。
  - 新增 `CONFIG_NAME = "knobs.json"` 与 `repo_config(root=None)`：当 `<repo>/knobs.json` 存在时读取顶层 JSON 对象（`{ "REFLECT_...": "..." }`）。
  - `get(name)`、`flag(name)`、`readme_names()`、`served_langs()`、`history_secs()` 统一按 `os.environ` > `repo_config(gate.GATE_REPO)` > `REGISTRY[name][1]` 解析。
  - 在 `knobs` 自检（及 `registry.problems()`）中校验 `knobs.json`：非合法 JSON、未知 `REFLECT_*` 键、或 `file`/`dir` 类型旋钮指向不存在的路径时报错。
- 仓库根新增 `/knobs.json`：
  ```json
  {
    "REFLECT_DOCS": "STATE.md,AGENTS.md,PRINCIPLES.md,README.md,README.zh.md,README.de.md",
    "REFLECT_READMES": "README.md,README.zh.md,README.de.md"
  }
  ```

### 1.3 完成判据（Batch 1）
- `python3 zreflect/knobs.py --selftest && python3 zreflect/registry.py --gates` 返回 `rc=0`，且工作区不存在 `Einfacht.env`、`einfacht-env.sh`、`check_envfile.py`。

---

## Batch 2：合并 `guard.py` / `render.py` 入 `ledger.py`，解耦 `RULES` 与 `FACTS.json`

### 2.1 删除清单
- 文件：
  - `zreflect/guard.py`
  - `zreflect/render.py`
- 符号与分支：
  - `zreflect/facts.py:493-496`：在 `measure()` 中删除 `if _has_principles_doc(): facts.update(doc.facts_of_rules())`。
  - `zreflect/check_facts.py:340-355`：删除 `principle_sync_problems()` 及 `zreflect/lang/{en,zh,de}/facts.json` 中的 `facts.principle_ledger_drift`。
  - `zreflect/render.py:41-45`（迁入 `ledger.py` 时）：删除 `if isinstance(v, dict) and v.get("kind") == "principle": continue` 过滤分支（`FACTS.json` 不再含 `principle.*`）。

### 2.2 修改与收拢
- `zreflect/ledger.py`：
  - 吸收原 `guard.py`（`write_target_problems`、`accepted_keys`、`decide`）与原 `render.py`（`BLOCK_BEGIN`、`BLOCK_END`、`render_block`、`render_doc`、`extract_block`、`strip_blocks`）及各自 `_cases*` 自测用例。
  - 更新 `zreflect/facts.py`、`zreflect/check_facts.py`、`zreflect/check_stale.py`、`zreflect/check_retractions.py`、`zreflect/echoes.py` 中的 `import guard` / `import render` 为 `import ledger`。
- `zreflect/check_facts_replay.py`：
  - 在 `replay_all(facts, ...)`（`check_facts_replay.py:118-150`）中，当 `doc.accepts_principles()` 为真时，将 `doc.facts_of_rules()` 合并入待复跑条目（共用 `_replay_one()`，不落盘至 `FACTS.json`）。
  - `zreflect/facts.py` 的 `--get principle.<id>` 与 `show principle.<id>` 直接从 `doc.facts_of_rules()` 读取并执行/展示。
- `zreflect/facts.py` 与 `zreflect/check_facts.py`：
  - 将 `block_homes(ledger)` 迁入 `check_facts.py`，`facts.py --check` 直接调用 `check_facts` 的机器块校验函数，消除两处重复的块比对实现。

### 2.3 完成判据（Batch 2）
- `FACTS.json` 中不含任何 `principle.*` 键；`python3 zreflect/ledger.py --selftest && python3 zreflect/check_facts.py --selftest && python3 zreflect/check_facts_replay.py --selftest && python3 zreflect/facts.py --selftest` 全部返回 `rc=0`。

---

## Batch 3：单入口 `reflect-hooks/hook.py` 与单层 `zreflect/seal.py`

### 3.1 删除清单
- 文件：
  - `reflect-hooks/pre-commit`
  - `reflect-hooks/pre-push`
  - `reflect-hooks/gate.py`（重命名为 `reflect-hooks/hook.py`）
- 符号与分支：
  - `reflect-hooks/install.py:123-135,140-142,165,194-195`：删除 `install_legacy()`、`--legacy` 分支及对应 `install.legacy_*` 语言包键。
  - `zreflect/criteria.py:69-70`：从 `ALLOWED_SHELL` 移除 `"reflect-hooks/pre-commit"` 与 `"reflect-hooks/pre-push"`。
  - `zreflect/seal.py:49-92,190-198,234-235,285-296`：删除 Tier-1 AST 切片（`_is_yardstick_stmt`、`_case_counts_in_node`、`_py_yardstick`、`yardstick_sha256`、`cases`、`red_cases`）及 `--reseal-yardstick` / `--allow-case-drop` 分支（含 `zreflect/registry.py:733-743` 与 `zreflect/lang/{en,zh,de}/registry.json` 中的 `seal.reseal_refused_*` / `seal.yardstick_tampered`）。
  - `zreflect/gate.py:491-601,607-616,646-648,658-689`：删除 `_find_helper_def`、`_direct_returns`、`_helper_constant_truthy`、`_fn_arg_names`、`_returned_helper_names`、`_imported_names`、`_missing_helper_reason`、`_helper_reason`、`_delegation_reason`、`_is_delegated` 及 `delegated` 统计行（含 `gate.never_falsifiable_delegated`、`gate.never_falsifiable_constant_return`、`gate.never_falsifiable_unresolved_helper`、`gate.selftest_delegated`）。

### 3.2 修改与修复
- `reflect-hooks/install.py`：
  - 使用 `git -C <repo> rev-parse --git-path hooks` 定位 hooks 目录（支持 git worktree 与 submodule，替代 `os.path.isdir(os.path.join(repo, ".git", "hooks"))`）。
  - 生成的链式脚本使用 `sys.executable` 绝对路径调用 `reflect-hooks/hook.py`；若存在 `$PREV`，先将 `stdin` 读入临时文件或内存分别喂给 `$PREV` 与 `hook.py`，防止 `pre-push` 丢失 ref 输入。
- `reflect-hooks/hook.py`（原 `reflect-hooks/gate.py`）：
  - 修复 `pre-push` 多提交崩溃（`hook.py:135-138,161-162`）：当 `rsha == ZERO_SHA` 时，将 `revs.splitlines()` 拆分为独立 SHA 参数列表传给 `git log --name-only --pretty=format:`。
  - 修复 `pre-commit` 部分暂存失步（`hook.py:194-204`）：若 `git diff --name-only -- FACTS.json` 非空（工作区 `FACTS.json` 有未暂存修改），拒绝自动运行 `--render-doc` 覆盖并报错退出（`rc=1`）；`git add` 仅暂存本次渲染产生变更的目标文档并校验返回码。
- `zreflect/seal.py`：
  - 单层结构：`SEAL.json` 的 `files` 仅记录 `{ "<rel>": { "file_sha256": "<hex>" } }`，`_merkle_root` 计算 `rel:file_sha256`。
  - `_load_seal` 严格校验每个 entry 为含 64 位十六进制字符串 `"file_sha256"` 的 `dict`，否则返回 `seal.corrupt`。
  - `verify_problems` 校验 `SEAL.json` 中记录的文件集合及 `MODULE` 声明的平台模块；下游仓库新增的不在 `SEAL.json` 中的 `zreflect/check_<custom>.py` 不报 `seal.unsealed_core_file`。
  - 仅保留 `--verify-seal` 与 `--reseal=PATHS`（支持 `ALL`）。
- `zreflect/gate.py`：
  - `never_falsifiable(fn)` 仅检查定位到的同源码行 `Lambda` 节点是否存在：(1) 函数体直接为真值/假值常量（`lambda: True`、`lambda: 1`、`lambda: "x"`），(2) `BoolOp` 常量短路（`or True`、`and False`），(3) 同表达式自比较（`x == x`）。

### 3.3 完成判据（Batch 3）
- `python3 reflect-hooks/install.py --selftest && python3 reflect-hooks/hook.py --selftest && python3 zreflect/seal.py --selftest && python3 zreflect/registry.py --selftest` 全部返回 `rc=0`。

---

## Batch 4：清理 `gates-selftest.sh`、修复 Windows 路径与 CI/文档同步

### 4.1 删除与修改
- 删除 `gates-selftest.sh`，并从 `zreflect/criteria.py:63` 的 `ALLOWED_SHELL` 与 `zreflect/seal.py:24,180` 中移除 `"gates-selftest.sh"`（`ALLOWED_SHELL` 仅保留 `"reflect-hooks/quality-record.sh"`）。
- 修复 Windows 路径与扫描边界：
  - `zreflect/doc.py:699`：`os.path.join(sub, f)` 改为 `sub + "/" + f`。
  - `zreflect/knobs.py:1268`：`repo_path("REFLECT_FACTS", "/r")` 断言改为 `os.path.join("/r", REGISTRY["REFLECT_FACTS"][1])`。
  - `zreflect/facts.py:145-147`：`measure_example()` 中用 `dirs[:] = [d for d in dirs if d != ".git"]` 替代 `if "/.git" in root:`。
  - `zreflect/check_explain.py:128`：在 `_suite_sources()` 中跳过 `name.startswith("measure_")` 的下游测量模块。
- 更新 `.github/workflows/gates.yml`：
  - 第一档增加 `python zreflect/registry.py --verify-seal`。
  - 第三档 `mypy` 将 `reflect-hooks/*.py`（`hook.py`、`install.py`）一并纳入检查列表，并开启 `--check-untyped-defs`。
  - 第五档 `shellcheck` 文件列表移除已删除的 `gates-selftest.sh`、`reflect-hooks/einfacht-env.sh`、`reflect-hooks/pre-commit`、`reflect-hooks/pre-push`。
- 同步 `AGENTS.md`、`README.md`、`README.zh.md`、`README.de.md` 及 `examples/`（移除 `Einfacht.env` / `--render-doc STATE.md` 旧说明，对齐 `knobs.json` 与 `reflect-hooks/hook.py`），重封 `SEAL.json`，运行 `facts.py --allow-drop --accept-changes` 与 `facts.py --render-doc`。

### 4.2 完成判据（Batch 4）
- 运行本单 `Settling:` 命令、`python3 -m ruff check .`、`python3 zreflect/examples.py --all`、四语言（null / `en` / `zh` / `de`）`python3 zreflect/harness.py` 及剩余 3 个 shell 文件的 `shellcheck` 全部返回 `rc=0`。
