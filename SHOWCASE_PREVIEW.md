# OpenResearch Hub Showcase 预览说明

## 正式代码位置

请在 VS Code 中打开：

    D:\huggingface_hub-main\atlas-platform

新版科研项目主页代码是：

    D:\huggingface_hub-main\atlas-platform\showcase.html

## 正确打开方式

不要双击 v10-staging 里的 HTML 文件。那个目录只是开发过程中的临时副本，直接用 file:// 打开时浏览器无法连接登录模块和后端接口。

启动 Docker 服务后，在浏览器打开：

    http://127.0.0.1:8000/resources/12/showcase

这是可给组长展示的正式页面。页面内容来自当前后端 API，包含项目数据、结果表格、引用信息和资源统计。

## 给组长展示

1. 在 Docker Desktop 中确认 atlas-platform-backend、PostgreSQL、Redis、MinIO 和 Gitea 已运行。
2. 打开上面的本地网址。
3. 使用浏览器截图工具截取 Hero、Research Overview、Results 和 Citation 区域。
4. 如果只展示代码，在 VS Code 中打开 showcase.html；如果展示运行结果，使用浏览器网址。

## 当前页面模块

- Research Hero 和项目封面
- Overview、Methodology、Contributions、Experiments、Results、Media、Citation 目录
- Research Information 侧栏
- 结果摘要卡片与最佳结果高亮
- 图片放大、视频、PDF、BibTeX Copy
- 原有 Showcase 编辑、媒体上传和结果表格管理功能

## 验证地址

- 页面：http://127.0.0.1:8000/resources/12/showcase
- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health
