# 01: 示例悬案 —— 两道守卫真的会拦住写盘吗

**What to build:** 验证 `zreflect/facts.py` 的**两道守卫**在真实台账上确实会红、且拒绝写盘。
（这张单存在的意义是给 `Settling:` 行做一次真实运行示范；看完可以删。）

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Settling:** zreflect/facts.py —— rc=0 ⇒ 两道守卫的断言全过，本单可结案；rc≠0 ⇒ 有断言失效，先修守卫

## 复跑方式

```sh
python3 zreflect/facts.py --selftest     # 两道守卫 + 文档一致性的断言
sh gates-selftest.sh --selftest          # runner 自己会红（4 类夹具）
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

- [ ] 跑上面两条，记录 rc
- [ ] 手工注入假值，确认守卫报错且**文件没被改**
- [ ] 结论回填，`Status:` 改 `resolved`，**别删这个文件**
