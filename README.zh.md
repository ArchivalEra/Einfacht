# Einfacht（原 zcode-reflect）

[![gates](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml)
[![readme-sync](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![checked by mypy](https://img.shields.io/badge/checked_by-mypy-2A6DB2)](https://mypy-lang.org/)
![python](https://img.shields.io/badge/python-3.13+-3776AB)
![license](https://img.shields.io/github/license/ArchivalEra/Einfacht)

**Agent 的记忆不该是散文，该是一条能复跑的断言。**

一套面向 agent 驱动仓库的反幻觉事实系统：每一句「现在是什么样」都必须
挂在一条可复跑的命令上、或标成推断并附结算命令、或进翻案台账。
三样都不沾 ⇒ 闸门红。

**语言：** [English](README.md)（默认）· **简体中文**（本文件）· [Deutsch](README.de.md)

## 怎么用

**给 AI agent：** 读 [skills/einfacht/SKILL.md](skills/einfacht/SKILL.md) ——
安装、接线、旋钮、闸门输出怎么读，全在那一份里。它是唯一入口，
本 README 不重复。

给人看的 30 秒版：

```bash
cp -r <suite>/zreflect <suite>/reflect-hooks <suite>/ruff.toml <你的仓>/
cd <你的仓>
python3 zreflect/facts.py --init                  # 生成骨架文档，不覆盖已有文件
python3 zreflect/facts.py                         # 量一遍
python3 zreflect/facts.py --render-doc            # 机器块渲染进状态文档
python3 reflect-hooks/install.py --chain          # 链进你已有的 git 钩子
set -a; . ./Einfacht.env; set +a                  # source 旋钮载体
python3 zreflect/registry.py --run commit         # 执行面唯一入口
```

你会得到：测量值只在 `FACTS.json` 生产一次（文档引用 `[[键名]]`，
永不手抄）、发现式登记的闸门名录在提交/推送时刻真跑、每道闸门三档
自证（`harness.py`）、带重现检测的翻案台账、开工前活性预检 doctor。

## 文档地图

| 想要 | 去看 |
|---|---|
| 教 agent 用它 | [skills/einfacht/SKILL.md](skills/einfacht/SKILL.md) |
| 本文件（简体中文） | README.zh.md —— 三语组：[README.md](README.md) · [README.de.md](README.de.md) |
| 给 agent 的硬规矩 | [AGENTS.md](AGENTS.md) |
| 现状与方向 | [maintaince.md](maintaince.md) |
| 测出的事实（机器块） | [STATE.md](STATE.md) |
| 语言包术语表 | [docs/LANG-PACK-GLOSSARY.md](docs/LANG-PACK-GLOSSARY.md) |

长版 README（设计论证 / 组件表 / 决策记录）在 git 历史里 ——
`git log -- README.md`。

## License

MIT
