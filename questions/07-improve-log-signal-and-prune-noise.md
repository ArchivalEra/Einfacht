# 07: 提升失败日志信息量、消除汇总重复与装饰噪音

**What to build:** 在不引入通用日志模块/抽象框架、保持“各套件自行直接输出 + 裸值 stdout 契约不变”的前提下，修正实测暴露的失败信息吞吐缺口、重复刷屏与花哨装饰，让失败时一条命令就能给出完整排障上下文：
1. **失败信号补全（不静默吞错）**：
   - `zreflect/gate.py` `run_phase()` 为 `fatal_list`（`rc==2`）与 `error_list`（`rc<0` 或 `rc>2`）同样保留输出至 `fail_out`；`zreflect/registry.py` `_main_run()` 对 `fatal_list` / `error_list` 与 `fail_list` 一并回显精简输出，并用 `M("registry.phase_failed", file=f)` 替代裸英文 `"  FAILED %s"`；
   - `zreflect/registry.py` `_emit_gate_output()` 最多回显前 `5` 条 `"  · "` 问题行（不足或无 `"  · "` 时保留非空报错行与尾行上下文），超出部分显式附加 `... (+N more)`（`M("registry.more_items", count=...)`），移除无调用方的 `"\u2139 "` 判断；
   - `zreflect/check_facts.py` 在 `_line_unaccounted()` / `_cite_problems()` / `_copied_fact_problems()` 中为 `facts.bare_number_unaccounted`、`facts.missing_key_cite`、`facts.copied_value` 传入 `file=doc_name`，使多文档扫描直接定位到具体文件名与行号；
   - `zreflect/check_facts_replay.py` 在 `replay.mismatch` 中传入 `command=cmd`（同步更新三语包模板）；
   - `zreflect/facts.py` `check_doc()` 仅在 `facts.markers_missing_check`（`rc==2`）使用 `fatal()`，在 `facts.block_stale` / `facts.extra_blocks_stale`（`rc==1`）向 `stderr` 打印全部过期问题文本而不误冠 `FATAL:`；`facts.py main()` 对未知命令只输出一条 `fatal(...)` 而不再先打整段 `usage`；
   - `zreflect/harness.py` `_tail()` 在非 selftest 崩溃且超长时保留头尾上下文，`_renamed_all_green()` 保留失败尾行并写入 `harness.rename_failed`；`zreflect/examples.py` `_step_problems()` 附带失败命令 `_one()` 按标题→细节顺序统一输出到 `stderr`。
2. **消除汇总重复与终端花哨装饰（去噪）**：
   - `zreflect/registry.py` `_main_run()` 将 `off_list` 聚合成单行 `M("registry.phase_off_list", count=..., files=...)` 并置于失败详情之后，不再每次提交刷出 6–7 行重复 `(off — never checked)` 样板、也不在末尾多打空行；
   - `zreflect/gate.py` `selftest()` 去除重复的 `human_summary`（保留唯一的 `emit_summary`），让单次自证与 `harness.py` 不再双倍复读摘要；
   - 统一清理 `zreflect/lang/{en,zh,de}.json` 与源码直印（`harness.*`、`registry.*`、`facts.py`、`check_facts_replay.py`）中的终端 Markdown 加粗 `**...**` 及花哨符号（`✓` / `✗` / `❌` / `──` / `----` / `⚠`），改为简洁纯 ASCII 状态标签，同时精简 `doctor.off` 重复说辞，保留 `harness.py` 的单层清晰结构。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 -c "import os,sys; sys.path.insert(0,'zreflect'); import check_facts,check_facts_replay,facts,gate,registry; ph=gate.run_phase('commit',['ok.py','off.py','bad.py','fat.py'],runner=lambda f:{'ok.py':(0,''),'off.py':(0,'OFF: x'),'bad.py':(1,'h\n  · p1\n  · p2\n  · p3\n'),'fat.py':(2,'FATAL: bad_cfg\n')}[f]); assert 'fat.py' in ph['fail_out'] and 'FATAL: bad_cfg' in ph['fail_out']['fat.py']; cf=check_facts.problems({'facts':{'n':{'value':1,'cmd':'c'}}},'p 999\n'+facts.render_block({'facts':{'n':{'value':1,'cmd':'c'}}}),doc_name='README.md'); assert cf and cf[0].params.get('file')=='README.md'; rp=[]; check_facts_replay._judge_ok('k',{'value':1,'cmd':'echo 2'},'echo 2','2',rp,{'ok':0}); assert rp and rp[0].params.get('command')=='echo 2'" && python3 -c "import json; packs=[json.load(open(f'zreflect/lang/{l}.json',encoding='utf-8')) for l in ('en','zh','de')]; bad=[(l,k) for l,d in zip(('en','zh','de'),packs) for k,v in d.items() if any(t in v for t in ('**','✓','✗','❌','──'))]; assert not bad, bad" && python3 zreflect/registry.py --verify-seal && python3 zreflect/registry.py --run commit && python3 zreflect/harness.py —— rc=0 ⇒ 失败日志（FATAL output/多条问题/文件名/复跑命令/block_stale rc=1）完整不吞错，off 已聚合为单行且语言包与输出已去花哨去重复；rc≠0 ⇒ 仍有失败上下文缺失、重复刷屏或花哨装饰残留

## 锁定边界（不可改动）

- **不新建通用日志模块**：不添加 `log.py` / `logger.py`，不为了“拓展性”扩张 `gate` 或 `i18n` 的通用参数接口；各套件模块保留各自的直接 `stdout`/`stderr` 输出责任。
- **裸值 stdout 契约不变**：`facts.py --get`、`facts.py --count`、`facts.py --render`、`next.py`、`doctor.py`（`ok`）等机械消费的 stdout 输出格式保持原样。
- **保留零语言与自证结构**：`M(code, **params)` 在无语言包时输出纯机器码；`gate.selftest()` 保留 `=== N PASS / M FAIL ===` 摘要行供 `harness.py` 解析；全部 19 道闸门语义与 `--run commit` 四态（`ran`/`off`/`failed`/`fatal`）报告完整保留。
