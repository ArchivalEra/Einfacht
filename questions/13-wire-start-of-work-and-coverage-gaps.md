# 13: 补齐 `start-of-work`、`hook`、`i18n` 与 `next.py` 执行面盲区

**What to build:** 把长期只在文档里存在、实际从不自动触发或存在检查盲区的角落全部接进执行面。

**Blocked by:** None (can start immediately)

**Status:** needs-triage

**Settling:** none -- first deliverable: 第一交付物是让 `registry --run start-of-work` 纳入 CI 且 `check_i18n` / `knobs` / `next` 覆盖全部盲区的验证用例

## 实测问题清单

1. **`start-of-work` 三道闸（`check_history`、`check_explain`、`doctor`）本地与 CI 双缺席**（`.github/workflows/gates.yml`、`reflect-hooks/hook.py`）：
   - 本地 `pre-commit`/`pre-push` 与 CI 都只跑 `registry --run commit`；注释超限（`check_explain`）与 `HISTORY` 隔离（`check_history`）在默认流程下从不执行。
2. **`check_i18n.py` 三处扫描盲区**（`zreflect/check_i18n.py`）：
   - `used_codes()` 只扫 `zreflect/`，漏扫 `reflect-hooks/hook.py` 使用的错误码；
   - 不校验语言包 value 是否为空字符串 `""` 或非英语包完全未翻译；
   - `# PINNED: <8字符>` 注释豁免阈值过低（任意 8 字符即可跳过非 ASCII/中文扫描）。
3. **单跑闸门绕过 `knobs.config_problems()`**（`zreflect/knobs.py`、`zreflect/facts.py`）：
   - 目前仅 `registry --gates`、`facts --render-doc`/`--check`、`check_facts` 检查 `knobs.json` 合法性；单独直接运行某道闸门时，错误键或布尔值会被 `repo_config()` 静默强转放过。
4. **`next.py` 超额静默截断 & `seal._skip_optional()` 边界**（`zreflect/next.py:150-192`、`zreflect/seal.py`）：
   - `next.py` 未结案单超过 `MAX_LISTED`（3 条）时直接截断丢弃，不像 commit 列表那样给出 `+N more` 提示。
   - `seal._skip_optional()` 当整个 `reflect-hooks/` 目录被删除时静默豁免已封存 hook 脚本的缺失。

## 待裁决设计点

1. `gates.yml` 补入 `registry --run start-of-work` 后，`doctor` 在无 `doctor.json` 时 `OFF:` 是否符合预期（CI 是否需要针对性配置或仅强制 `check_history` + `check_explain`）？
2. `knobs.config_problems()` 是否在公共入口（如 `gate.activate_or_fatal()`）统一兜底校验？

## 复跑方式

```sh
python3 zreflect/registry.py --run start-of-work && python3 zreflect/check_i18n.py
```
