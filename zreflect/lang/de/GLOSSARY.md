# 德语包翻译术语表（`zreflect/lang/de/`）

这是**词汇表**，不是风格指南：所有分片必须用它，否则同一个概念在 23 个文件里
会出现 23 种德语说法 —— 那就是口径漂移。

## 硬约束（违反即闸门红）

1. **占位符名逐字保留**：`%(name)s` → `%(name)s`。格式说明符（`d` / `s` / `r`、
   宽度修饰如 `%-24s`）也逐字保留。**只翻混凝土字**。
2. **值不得以机器契约形状开头**（`i18n._CONTRACT_SHAPES`）：
   `^[A-Z][A-Z0-9_]*:`（`OFF:` / `FATAL:` / `DOWN:` / `SKIP:`）、`^===`、
   `^PASS \| `、`^fail \| `。这些串在发射点用字面量，语言包结构上不许产出它们。
3. **JSON 键必须与 `en/` 侧完全一致**（`knobs.pack_sync_problems()` 会报差集）。
4. `--` 与 `—`（破折号）可以照搬英文的用法；不要引入英文里没有的标点。
5. 参数名是 null 包的契约（`key` 不是 `k`），**参数名不翻译**。

## 术语表（英文 → 德语）

| 英文 | 德语 |
|---|---|
| gate | Tor（复数 Tore） |
| checker | Prüfer |
| ledger | Register |
| fact | Fakt（复数 Fakten） |
| living state | Lebendzustand |
| measure / measurement | messen / Messung |
| re-measure | neu messen |
| replay | Wiederholung（"re-run" 用 `neu ausführen`） |
| machine block | Maschinenblock |
| self-test | Selbsttest |
| assertion | Zusicherung |
| falsifiable | widerlegbar |
| zero-value guard | Nullwert-Wächter |
| knob (REFLECT_*) | Knopf (REFLECT_*) |
| carrier (Einfacht.env) | Träger |
| registry / roster | Verzeichnis / Namensliste |
| discovery-based | entdeckungsbasiert |
| pin | Pin |
| world | Welt |
| instrument | Messinstrument |
| invariant | Invariante |
| retraction | Widerruf |
| stale | veraltet |
| provenance | Herkunft |
| provenance marker | Herkunftsmarke |
| bare value | nackter Wert |
| bare number | nackte Zahl |
| shape whitelist | Formular-Whitelist |
| whitelist / blacklist | Whitelist / Blacklist |
| drift | Drift |
| declare / declaration | deklarieren / Deklaration |
| reconcile / reconciler | abgleichen / Abgleicher |
| phantom / typo | Phantom / Tippfehler |
| orphan | Waise |
| exit code / rc | Rückgabewert / rc |
| phase (commit / start-of-work) | Phase (commit / start-of-work) |
| start-of-work | Arbeitsbeginn |
| hook | Hook |
| pre-commit / pre-push | pre-commit / pre-push |
| worktree / repo root | Arbeitsbaum / Repo-Wurzel |
| commit sha | Commit-SHA |
| live run | echte Ausführung |
| regression | Regression |

## 语气

原文的语气是**直陈 + 因果链**（"X 不存在 ⇒ Y"），常常带**修法提示**
（"⇒ 跑 `python3 zreflect/facts.py`"）。德语照搬这个结构：

- 用 `⇒` 保留因果指向
- 保留反引号包围的命令 / 键名 / 文件名
- 不要加礼貌用语（原文没有）
- 不要扩写成完整句（原文是压缩电报体）；保留短句与分号
