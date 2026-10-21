# 前端 CI：自动检查类型和构建

## 1. 为什么加入这项检查

后端测试通过，只能说明现有后端测试覆盖的行为符合预期。前端仍可能存在 TypeScript 类型错误、Vue 组件编译错误或构建失败。

本次增加 `.github/workflows/frontend-ci.yml`，将已经在本机执行过的安装和构建命令放到 GitHub 上重复执行。

## 2. 两条工作流怎样配合

| 工作流 | 检查名称 | 主要任务 |
|---|---|---|
| Backend CI | Backend unit tests | 安装 Python 依赖，运行当前后端回归测试 |
| Frontend CI | Frontend build | 安装 Node.js 依赖，检查类型并构建前端 |

两条工作流分别报告结果。它们都监听向 main 的 push、以 main 为目标的 pull_request，以及手动 workflow_dispatch。

推送开发分支后，创建以 main 为目标的 PR，会触发这两条检查。前后端没有相互等待的配置，可以由 GitHub 根据可用执行资源并行调度。

## 3. 前端工作流的四个步骤

### Checkout code

将本次待检查的代码取到 GitHub 的临时执行环境中。

### Set up Node.js 24

`actions/setup-node@v6` 准备 Node.js 24，并配置 npm 缓存。

- `@v6` 是准备环境这个 Action 的版本。
- `node-version: "24"` 是要运行项目的 Node.js 主版本，与现有前端 Dockerfile 使用的 Node.js 主版本一致。
- `cache-dependency-path: frontend/package-lock.json` 用锁文件参与生成缓存键；锁文件变化时，缓存键也变化。
- 缓存不等于可以跳过安装，后续仍然执行 npm ci。

第一版使用已核对的官方 v6 标签。与后端工作流一样，后续可以在经过审核后固定完整提交 SHA，并配合版本更新维护。

### Install locked dependencies

先打印 Node.js、npm 版本，再执行：

```text
npm ci --no-audit --no-fund
```

打印版本有助于定位“本机能运行、CI 却失败”的差异。

npm ci 按锁文件安装整个依赖树；package.json 与锁文件不一致时会报错，不会自动帮我们改锁文件。这一步检查依赖安装是否可重复。

### Type check and build

执行：

```text
npm run build
```

目前 package.json 中的 build 是：

```text
vue-tsc -b && vite build
```

先检查类型，成功后再构建。这个名称是 Frontend build，不表示已经执行了页面交互测试。

## 4. 为什么命令里没有 cd frontend

```yaml
defaults:
  run:
    working-directory: frontend
```

这个配置已经让每条 run 命令在 frontend 目录执行。

uses 类型的 Action 不受该设置影响，因此缓存锁文件的路径依然从仓库根目录写为 frontend/package-lock.json。

## 5. 如何提交这次改动

本次工作分支：ci/frontend-checks。

在项目根目录的 CMD 中执行：

```bat
git add .github/workflows/frontend-ci.yml deploy/前端CI说明.md
git commit -m "ci: check frontend types and build"
git push -u origin ci/frontend-checks
```

在 GitHub 创建 PR：base 为 main，compare 为 ci/frontend-checks。

建议标题：ci: check frontend types and build。

建议说明：增加前端 CI 和教学文档；本机 npm ci、npm run build 已执行通过；等待 GitHub 上 Backend unit tests 和 Frontend build 的结果。

## 6. 怎样验收

1. Files changed 只有新工作流和本说明文件。
2. Backend unit tests 成功，确保已有检查继续运行。
3. Frontend build 成功；展开 Type check and build，应看到构建成功输出。
4. 审阅后合并，再回到本地 main 拉取更新。

本机已构建成功，是本机环境中的证据。首次 GitHub 运行成功，才是 GitHub Linux 环境中的证据。

## 7. 常见失败怎样定位

| 失败步骤 | 排查重点 |
|---|---|
| Set up Node.js 24 | Action 是否被允许、运行环境和 Node.js 下载 |
| Install locked dependencies | 具体依赖下载地址、锁文件一致性、Node/npm 版本、平台可选依赖 |
| Type check and build | 先阅读报错文件名、行号、类型或编译错误 |

出现安装失败时保留锁文件和报错，不要直接删除锁文件或用另一条安装命令绕过检查；应先找到失败原因。

## 8. 检查范围

这条工作流验证依赖安装、类型检查和前端构建。生成的 dist 位于临时执行环境中，当前工作流没有发布部署步骤。

登录、提交、轮询、下载等交互仍需对应测试；真实模型和完整 PPT 制作仍需业务验收。

参考：

- [GitHub Node.js CI 教程](https://docs.github.com/en/actions/tutorials/build-and-test-code/nodejs)
- [setup-node v6](https://github.com/actions/setup-node/tree/v6)
- [npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/)
