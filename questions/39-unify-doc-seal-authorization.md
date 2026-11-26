# 39: 裁决 doc.py 的套件封印授权

**What to build:** `zreflect/doc.py` 已列入 `SEAL.json`，Trust 还用 `principles.doc_py_sha256` 检查该文件并要求 `seal.doc`。评估能否由套件授权统一覆盖该文件。

**Blocked by:** None -- Owner 已裁决并允许与 Q40 并行落地。

**Status:** resolved

**Settling:** python3 zreflect/trust_core.py --selftest && python3 zreflect/trust.py --selftest -- rc=0 => doc.py governed solely by SEAL.json/SUITE.sig, seal.doc retired, legacy doc_py_sha256 cleaned; rc!=0 => Q39 regression

## 裁决与实施结论

- 彻底废除 `seal.doc`：`zreflect/doc.py` 统一只受 `SEAL.json` + `SUITE.sig`/`seal.core` 保护。
- `lock_core=false` 不再单独拦截 `doc.py`，仅保留 `principles.edit`（`PRINCIPLES.md`）与 `principles.disable`（`REFLECT_NO_PRINCIPLES`）。
- 旧 `ANCHORS.json` 中的 `principles.doc_py_sha256` 在 `--migrate`、`--upgrade` 与 `--sync` 时自动清理；`heads` 中仍含旧 `doc_py_sha256` 的历史锚点在比对时免审批兼容。
