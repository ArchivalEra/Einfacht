# 18: Spec 配置型闸门与探针漏洞（`ab` / `invariants` / `instruments` / `locks` / `pins` / `secrets` / `world` / `doctor`）

**What to build:** 修复 8 个 Spec 配置型闸门中的类型崩溃、空规则静默通过、字符串匹配绕过、路径逃逸、密钥漏扫与 HTTP/端口探测失真。

**Blocked by:** None (can start immediately)

**Status:** needs-triage

**Settling:** none -- first deliverable: 第一交付物是一组覆盖 8 道 Spec 闸门的失效回归用例（含 `must_contain: [""]`、`secrets` 首字节 `\x00` 与 `"secret"` 豁免、`pins` 缺第 4 token、`doctor` 3xx/4xx 与 `::1`）

## 实测问题清单

1. **`check_ab.py` 非 dict 崩溃与 `allow` / `None` 混淆**（`zreflect/check_ab.py:73, 86, 91, 121`）：
   - `ab.json` 非 dict/list 时 `AttributeError` 崩溃；`allow` 若传字符串 `"malloc"` 会被 `set(...)` 拆成单字符集；`da.get(k) != db.get(k)` 把 `null` 与缺键都当 `None` 放行；且未按文档校验 `allow` 键同时存在于双方。
2. **`check_invariants.py` 空片段、非字符串强转、非 UTF-8 崩溃与路径穿越**（`zreflect/check_invariants.py:63, 73-89, 95-113, 128`）：
   - 允许 `must_contain: [""]` 或空列表 `[]` 无条件通过；`str(c.get("path"))` 强转数字/列表；遇非 UTF-8 文件抛 `UnicodeDecodeError` 未被捕获；无仓库根 containment 检查且跟随软链接（可读取仓外文件）。
3. **`check_instruments.py` 缺失 `first_seen`、`NaN` 天数与子串绕过**（`zreflect/check_instruments.py:68, 89-97, 109, 119-125, 174`）：
   - 条目省略 `first_seen` 或 `REFLECT_INSTRUMENT_DAYS=nan` 直接使恒定性检测失效；`text in cmd` 可被多空格、换旗标序、引号或包裹脚本绕过；`{"methods": []}` 静默通过。
4. **`check_locks.py` `sha256` 校验缺失与 `form` / 文件系统类型错配**（`zreflect/check_locks.py:61, 71-84, 97`）：
   - 不校验 `sha256` 为 64 位小写 hex（非字符串会 `TypeError`）；`form="dir"` 指向普通文件可通过，未知 `form` 走文件分支遇目录抛 `IsADirectoryError`。
5. **`check_pins.py` 跳过脏检、`shell=True` 与版本子串误命中**（`zreflect/check_pins.py:61-67, 84, 97, 108, 118, 123`）：
   - 缺第 4 token（`len(parts) <= 3`）时跳过脏树检查；自建 `_run(shell=True)` 未引用 `worktree` 也未走 `gate.run_cmd`；`expect_version in first` 把 `"1.0"` 匹配到 `"1.0.99"`；缺字段时静默跳过或 `KeyError`。
6. **`check_secrets.py` `PLACEHOLDER` 过宽、软链接与 `\x00` 跳过**（`zreflect/check_secrets.py:56-59, 116-128, 163-166`）：
   - `PLACEHOLDER` 放行孤立词 `"secret"`/`"password"`/`"token"` 以及任意 `example-...`/`your_...` 前缀真实密钥；软链接仅计数不扫；文件前 8192 字节含单个 `\x00` 即被判定为二进制而整文件跳过。
7. **`check_world.py` 非空错误路径崩溃 & 分支逃逸**（`zreflect/check_world.py:173-181, 263-267`）：
   - `probs` 非空且 `resolve_line` 返回 `None` 时，提前求值 `ok_msg` 触发 `AttributeError` 崩溃；detached `HEAD`、未列入 `lines` 的特性分支或设置不匹配 `REFLECT_WORLD_LINE` 时跳过分支校验。
8. **`doctor.py` IPv6 漏检与 HTTP 重定向/`HTTPError` 掩盖**（`zreflect/doctor.py:121-130, 147, 171`）：
   - `port-free` 只连 `127.0.0.1` 漏掉 `::1`；`urlopen` 默认跟随 3xx 且 4xx/5xx 先抛 `HTTPError`，导致 `expect_status: 302/401/404` 无法判断；未限定 `http://`/`https://` 协议。

## 复跑方式

```sh
python3 zreflect/check_secrets.py --selftest && python3 zreflect/check_world.py --selftest && python3 zreflect/doctor.py --selftest
```
