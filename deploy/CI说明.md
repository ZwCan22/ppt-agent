# 第一条 CI：让 GitHub 自动运行后端测试

## 1. 本节目标

本地测试已经能运行，但每次需要你自己记得执行。现在把运行步骤写成 GitHub Actions 工作流，代码推送或提出合并请求时，自动获得一份检查结果。

工作流位置：`.github/workflows/backend-ci.yml`。这是 GitHub Actions 识别工作流的目录。

## 2. 什么时候执行

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
```

- `push`：向 main 推送提交时执行。
- `pull_request`：向 main 提出合并请求，以及请求更新时执行。
- `workflow_dispatch`：允许从 Actions 页面手动启动；文件要先进入默认分支。

当前没有配置定时运行。

## 3. 程序在哪里执行

`runs-on: ubuntu-24.04` 表示在 GitHub 托管的 Ubuntu 临时执行环境中运行。

它取到的是 GitHub 上的代码，不会直接访问你电脑里的 Docker、数据库、Dify 或 Ollama。

`timeout-minutes: 10` 给整个任务设置时间上限，避免异常等待。

## 4. 四个步骤分别做什么

| 步骤名称 | 作用 |
|---|---|
| Checkout code | 把本次待检查的代码取到执行环境 |
| Set up Python 3.13 | 准备 Python 3.13，并启用 pip 缓存 |
| Install locked dependencies | 按锁文件安装依赖，并检查依赖关系 |
| Run backend tests | 执行我们已经写好的五项回归测试 |

`uses` 调用别人已经写好的 Action；`run` 执行命令。

`actions/setup-python@v6` 中的 v6 是 Action 的版本；`python-version: "3.13"` 才是 Python 的版本。

第一版使用已经核对存在的官方 v6 标签。后续维护可将 Action 固定为经过审核的完整提交 SHA，并配合自动更新，进一步控制依赖版本。

## 5. 为什么有两个不同的依赖文件路径

```yaml
defaults:
  run:
    working-directory: backend
```

这相当于每条 `run` 命令执行前，都先进入 backend。因此 pip 命令直接使用 `requirements.lock.txt`。

`uses` 步骤不受这个目录设置影响。Python Action 的缓存配置要写仓库根目录下的路径：`backend/requirements.lock.txt`。

缓存用于减少重复下载，真正安装依赖时仍会执行 pip，并遵守锁文件中的版本。

## 6. 为什么不在 CI 里执行 test.cmd

test.cmd 是 Windows CMD 的入口，而这次 CI 使用 Linux。两边实际执行的是同一条 Python 测试命令：

```text
python -B -m unittest discover -s tests -t . -v
```

命令在 backend 目录中运行。测试通过模拟 HTTP 响应隔离 Dify，使用假配置，因此不需要上传真实 `.env` 或配置业务服务密钥。

## 7. 其他设置

- `permissions: contents: read`：只给工作流读取代码的权限。
- `persist-credentials: false`：取完代码后不保留供后续 Git 操作使用的认证配置。
- `concurrency`：同一工作流、同一分支或 PR 的新检查开始后，取消还没结束的旧检查，优先检查最新代码。

这条工作流只安装后端依赖并运行测试，没有发布或部署步骤。

## 8. 如何提交并查看结果

在 CMD 中执行：

```bat
cd /d D:\project\ppt-agent
git add .github/workflows/backend-ci.yml deploy/CI说明.md
git commit -m "ci: run backend tests on GitHub Actions"
git push
```

进入 GitHub 仓库的 Actions 页面，找到 `Backend CI`，打开刚推送的提交对应的运行，再打开 `Backend unit tests`。

点击 `Run backend tests`，应能看到 `Ran 5 tests` 和 `OK`；整个任务显示绿色。

## 9. 红色时先看失败在哪一步

| 失败步骤 | 先检查什么 |
|---|---|
| Checkout code | 仓库访问、Action 是否被组织策略限制 |
| Set up Python | Python 下载、Action 版本、执行环境 |
| Install locked dependencies | 具体下载失败、找不到哪个版本、是否有兼容 wheel、依赖冲突 |
| Run backend tests | 失败的测试名称、实际结果和期望结果 |

如果是依赖安装失败，不要通过删除业务断言或忽略失败来获得绿色结果；先处理真正失败的步骤。

若没有自动运行，检查文件是否已经推送到 main、Actions 是否启用、仓库或组织策略是否允许这些 Action，以及账户的运行额度提示。

## 10. 绿色结果的范围

它说明本次代码在 CI 环境里通过了当前这组测试。它不代表所有业务功能、真实模型可用性、Docker 部署或完整 PPT 生成都已经验收。

当前工作流只报告结果。把检查设为合并必须通过的条件，还需要后续配置分支规则，并确认仓库账户支持相关功能。

参考：

- [GitHub Python CI 教程](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [GitHub 工作流语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [官方 checkout v6](https://github.com/actions/checkout/tree/v6)
- [官方 setup-python v6](https://github.com/actions/setup-python/tree/v6)
