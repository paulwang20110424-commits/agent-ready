<h1 align="center">agent-ready</h1>

<p align="center"><b>你的代码库，准备好交给 AI 编程助手了吗？</b><br>
一条命令，16 项检查，一个 0–100 分，以及一枚可以提交进 README 的徽章。</p>

<p align="center">
  <a href="assets/agent-ready.svg"><img alt="agent-ready score" src="assets/agent-ready.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.8+" src="https://img.shields.io/badge/python-3.8%2B-blue.svg">
  <img alt="零依赖" src="https://img.shields.io/badge/dependencies-0-brightgreen.svg">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/README-English-blue.svg"></a>
</p>

---

## 一个没人量过的缺口

你把仓库交给 Claude Code、Cursor、Codex 或 Aider。它读了 README、grep 了一下测试命令、开始猜、
改错了文件——然后你花了二十分钟，跟一台**永远不会提问**的机器解释你自己的项目。

这个成本是结构性的：**AI agent 是一个永远不能问问题的"新人"**。它不能问程序从哪启动、测试怎么跑、
四个配置文件里哪个才是真的、`dist/` 是不是源码。每一个没被写下来的答案，都会变成"探索"——
而探索正是你真正在花钱买的东西（token、延迟、错误修改）。

`agent-ready` 量的就是这个缺口：**agent 需要的信息，有多少真的被写在了仓库里？**
输出一个分数、一个等级，以及按得分排序的最短修复清单。

## 拿一个你熟悉的项目试试

```console
$ python3 agent_ready.py ~/code/flask
```

```
      C   65.0 / 100

  FRONT DOOR     █░░░░░░░░░   4.0 / 36
    ✗  Agent instructions file          no AGENTS.md, CLAUDE.md, .cursorrules or copilot instructions
    !  README quickstart with commands  README.md has some commands, but not a full install → run path
    ✗  llms.txt index                   no llms.txt
  RUN RELIABLY   ██████████  28.0 / 28
    ✓  One obvious way to run tests     pyproject.toml test config · 48 test files
    ✓  Dependency lockfile committed    uv.lock
    ✓  CI runs the checks               .github/workflows
    ✓  Runtime version is pinned        .devcontainer/devcontainer.json
  NAVIGABLE      █████████░  21.0 / 24
    !  Files small enough to reason     2 files over 1,500 lines (20% of all code)
  HYGIENE        ██████████  12.0 / 12
    ✓  Types are checked                pyproject: mypy/pyright
```

请再读一遍：**Flask 在"可运行性"上拿满 28/28，在"门口"上只拿 4/36。**
锁文件、CI、devcontainer、类型检查、48 个测试文件——无可挑剔。可一个 agent 进来，
依然得自己反推"从哪里开始"，因为这些知识没写在它第一眼看的那一个地方。

这不是在批评 Flask。这是一种大概十八个月前才出现的**新债务**，而至今没人量它。

## 我们扫了那些最有名的仓库

| 仓库 | 分数 | 等级 | 最大缺口 |
|---|---|---|---|
| flask | 65 | **C** | 没有任何 agent 说明（门口 4/36） |
| fastapi | 59 | **C** | 缺说明 + 目录不可发现 |
| opencode | 65 | **C** | 缺说明 + 巨石文件 |
| express | 48 | **D** | 没锁文件、没固定运行时、没说明 |
| 一个 56.7 万行的 TypeScript 单体仓库 | 82 | **B** | 巨石文件、没固定运行时 |

**一个 A 都没有。** 这些都是成熟、口碑极好的项目，而每一个都至少让 agent 猜六件事。
觉得你的仓库不一样？一条命令：

```bash
curl -fsSLO https://raw.githubusercontent.com/paulwang20110424-commits/agent-ready/main/agent_ready.py
python3 agent_ready.py .
```

## 快速开始

零依赖、不需要 API key、不联网、不要账号。Python 3.8+。

```bash
# 1. 什么都不用装——它就是一个文件
curl -fsSLO https://raw.githubusercontent.com/paulwang20110424-commits/agent-ready/main/agent_ready.py
python3 agent_ready.py .

# 2. 或者装成命令
pipx install "git+https://github.com/paulwang20110424-commits/agent-ready"
agent-ready ~/code/my-app

# 3. 或者 clone 下来
git clone https://github.com/paulwang20110424-commits/agent-ready && cd agent-ready
make test
```

## 16 项检查（共 100 分）

| 区域 | 分值 | 它在问什么 |
|---|---|---|
| **门口** | 36 | 有没有 `AGENTS.md`？里面有没有**能直接跑的命令**？README 有没有真正的 quickstart？有没有 `llms.txt`？说明文件是"地图"（20–500 行）还是"手册"？ |
| **可靠运行** | 28 | 有没有唯一可发现的测试命令？锁文件提交了吗？配了 CI 吗？运行时版本固定了吗？ |
| **可导航** | 24 | 目录可预测吗？有没有超过 1500 行的文件？入口找得到吗？有真正的测试套件吗？ |
| **卫生** | 12 | 有没有把构建产物提交进来？类型检查开严格模式了吗？依赖钉死了吗？ |

为了让规则对真实项目公平，我们改了好几版：

- **零依赖项目**不该因为没有锁文件而扣分。
- 小型单文件工具用**扁平布局**是合理的，`src/` 不是强制的。
- `sympy/`、`django/`、`requests/` 这种包目录布局和 `src/` 同等对待。
- `python -m unittest`、`make test`、`cargo test`、`go test` 都算一等公民测试命令。
- 一个 400 行的测试文件算真实套件，三个空壳测试文件不算。

`agent-ready . --rules` 打印完整评分表，`--json` 给出全部数字。

## 不只是找问题，还能直接修

`--init` 会**根据你仓库里真实存在的东西**生成 `AGENTS.md`：你用的包管理器对应的安装/测试命令、
你的入口文件、你的目录结构、以及真正重要的规则。没有模板、没有套话、不调 API。

在一个完全没有 agent 说明的真实仓库上，一条命令把它从 **C 61 提到 A 85**。

生成的文件里只包含关于你仓库的**真话**——这已经比大多数手写的说明文件做得好了。

## 把徽章挂进你的 README

`--badge` 输出一个静态 SVG，提交进仓库、引用它、完事——不需要服务器、不需要账号、不会过期。

```bash
python3 agent_ready.py . --badge assets/agent-ready.svg
```

```markdown
[![agent ready](assets/agent-ready.svg)](https://github.com/你/你的仓库)
```

徽章上是**真实的**等级和分数，改进后重新生成即可。它天然诚实：数字是从你的代码树重新算出来的，
不是手填的。

## 在 CI 里卡住它

```yaml
- name: Agent readiness must not regress
  run: python3 agent_ready.py . --fail-under 85
```

分数掉了就 red。配合 `--json` 还能画趋势。

## 用法

```
agent-ready [ROOT] [选项]

      --init               根据仓库实际内容生成 AGENTS.md
      --badge [PATH]       输出 SVG 徽章（默认 agent-ready.svg）
      --md [PATH]          输出 markdown 报告（默认 AGENT_READINESS.md）
      --json               机器可读输出，给工具和 agent 用
      --rules              打印完整评分表后退出
  -v, --verbose            解释每项检查及其修复方式
      --fail-under N       分数低于 N 时退出码为 1（给 CI 用）
      --no-color           关闭颜色
      --version
```

## 为什么这个分数可信

- **确定性的。** 同一个代码树，永远同一个分数。没有 LLM、没有采样、没有抖动。
- **可解释的。** 每项检查都打印它用了什么证据（`AGENTS.md: 150 lines`、
  `2 files over 1,500 lines (20% of all code)`）、为什么重要、怎么修。
- **可审计的。** `--rules` 打印全部 100 分。不同意某个权重？那就是一个带着数字的讨论，欢迎开 issue。
- **本地的。** 永不联网；除非你显式加 `--init` / `--md` / `--badge`，否则不写你的仓库。

## 它不是什么

- **不是代码质量分。** 代码写得再漂亮，扁平目录 + 没有测试命令，agent 照样迷路。
- **不是安全审计。** 它不查漏洞。
- **不是完美的。** 检测是启发式的，奇怪的布局可能漏判。如果分数让你觉得不对，那是个值得报的 bug——
  有几条规则就是因为真实项目才被重写的。

## 自我审计（dogfood）

这个仓库用它自己审计，顶部的徽章就是它生成的：

```console
$ python3 agent_ready.py .
      A+  96.0 / 100
```

差的 4 分是还没接上的类型检查。我们本可以加个配置文件凑满 100——但那恰好毁掉这件事的意义。

## 贡献

整个工具就是 `agent_ready.py`。加一条规则 = 一个返回证据/理由/修复的 `check_*` 函数 + 一个测试。
权重之和必须保持 100，跑 `make ci`，不要加依赖。

```bash
make test    # 27 个测试，不到 1 秒，零依赖
make audit   # 用它自己审计这个仓库
```

## 许可证

MIT。随便用、随便发、随便嵌进你自己的工具里。

---

<p align="center">
  <b>在你的仓库上跑一次。如果分数扎心，修复清单就在下面。</b><br>
  <sub>English version: <a href="README.md">README.md</a></sub>
</p>
