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

当前测试覆盖大纲接入的正常响应和异常响应处理。

## 数据备份

```bat
deploy\backup.cmd
```

详细步骤见 deploy 目录中的备份说明。