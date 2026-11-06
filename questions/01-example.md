# 01: 示例悬案 —— 两道守卫真的会拦住写盘吗

**What to build:** 验证 `zreflect/facts.py` 的**两道守卫**在真实台账上确实会红、且拒绝写盘。
（这张单存在的意义是给 `Settling:` 行做一次真实运行示范；看完可以删。）

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** zreflect/facts.py —— rc=0 ⇒ 两道守卫的断言全过，本单可结案；rc≠0 ⇒ 有断言失效，先修守卫

## 复跑方式

```sh
python3 zreflect/facts.py --selftest     # 两道守卫 + 文档一致性的断言
python3 zreflect/harness.py --selftest   # runner 自己会红
```

想手工看守卫真会拦（这是本单真正想问的）：

```sh
cp FACTS.json /tmp/facts.bak
# 往里注入一个假值，再重测 —— 守卫必须报「旧值 → 新值」并且**不写盘**
python3 - <<'PY'
import json; p='FACTS.json'; d=json.load(open(p))
d['facts']['py_files']['value'] = 999
json.dump(d, open(p,'w'), indent=1, ensure_ascii=False)
PY
python3 zreflect/facts.py; echo "rc=$?"      # 期望 rc=2；且文件里仍是 999（拒绝写盘）
cp /tmp/facts.bak FACTS.json
```

**Type:** task

- [x] 跑上面两条，记录 rc：`--selftest` rc=0、`harness --selftest` rc=0
- [x] 手工注入假值（`py_files=999`），确认守卫报错且**文件没被改**：实测 `rc=2`，输出 `FATAL: guard.changed_row(after='35', before='999', key='py_files')` + `guard.refuse_changed_advice`，注入的 999 仍在盘上 ⇒ 拒绝了写盘；还原后 md5 与注入前一致（a0bd2202…）
- [x] 结论回填，`Status:` 改 `resolved`，**别删这个文件**

## 结论

两道守卫真的会拦，而且拦在写盘**之前**：报的是「旧值 → 新值」而不是笼统的
「不一致」，盘上的文件保持注入时的样子（没有被一次盲写覆盖成测量值）。
这正是它们与 `--check` 的分工 —— `--check` 只说「文档与台账对不上」，
守卫说的是「有人要悄悄改掉一行已发布的值」，并且拒绝动手。
