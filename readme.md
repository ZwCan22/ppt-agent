# PPT Agent

输入主题、听众、页数和要求，自动生成 PPT 并提供下载。

## 项目组成

- frontend：用户界面。
- backend：接口、用户认证、任务管理和 PPT 渲染。
- Worker：从队列领取任务并执行制作。
- Dify：生成 PPT 大纲。
- PostgreSQL：保存用户、任务和运行结果。
- deploy：部署配置和运维脚本。

## 本机启动

适用于已经完成环境配置和镜像构建的本机环境。

在项目根目录的 CMD 中执行：

```bat
deploy\start.cmd
```

网页地址：http://127.0.0.1:18080/

## 运行后端测试

```bat
deploy\test.cmd
```

当前包含 5 项大纲接入单元测试，以及 30 项 PostgreSQL 集成测试，覆盖权限、登录会话、任务历史、幂等与并发提交、Worker 租约和真实数据库迁移。

完整本机验收（先完成 Python 和前端依赖安装）：

```bat
deploy\test-all.cmd
```

该入口准备独立测试数据库，再执行后端测试和前端类型检查/构建；不启动业务 Worker 或调用真实模型。

## 数据备份

```bat
deploy\backup.cmd
```

详细步骤见 deploy 目录中的备份说明。

## 交付与学习文档

- [交付与维护手册](deploy/交付说明.md)：首次部署、配置、升级、恢复、排错。
- [集成测试说明](deploy/集成测试说明.md)：测试分类和隔离方式。
- [开发复盘](deploy/开发复盘.md)：分层、事务、幂等、测试与 CI，以及学习路线。
- [本轮验收记录](deploy/验收记录.md)：实际结果与验证边界。

## 架构

Vue 页面经 Nginx 访问 FastAPI；API 保存任务到 PostgreSQL；独立 Worker 领取任务、调用 Dify、校验大纲并生成 PPTX；页面轮询任务编号，完成后通过 API 下载共享存储中的文件。

## 当前交付范围

本版本适用于本机 Docker 教学环境。Compose 端口绑定本机，使用 development Cookie 配置。公网 TLS、容量压测和真实浏览器端到端自动化尚未验收，需结合实际部署目标推进。Dify DSL、密钥、数据库与 PPT 文件不包含在源码仓库中。
