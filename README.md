# Yasumi Clock

Yasumi Clock 是一款会主动打断长时间专注的跨平台桌面计时器。它的目标不只是提醒时间结束，而是帮助使用者从卡住、疲劳或无意义的持续投入中真正停下来休息。

当前版本使用 **Tauri 2 + Rust + React + TypeScript + Vite**。旧版 Python/PyQt 实现已于 2026-08-18 退出当前源码树；历史版本仍可从 [GitHub Releases](https://github.com/MrXnneHang/Yasumi-Clock/releases) 和 Git 历史中获取。

## 当前功能

- 自主开始、暂停、继续和结束专注计时
- 专注自然结束后自动进入按专注时长推导的休息阶段
- 独立设置窗口与置顶休息覆盖层
- 版本化设置和基于事件的会话历史
- 内置动画与本地动画媒体库
- Windows 和 macOS 便携版发布流程

## 开发环境

- [Node.js](https://nodejs.org/) 22.13.0 或更高版本
- [Rust](https://www.rust-lang.org/tools/install) 1.85 或更高版本
- 当前平台所需的 [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)

安装前端依赖：

```bash
npm ci
```

启动完整桌面应用：

```bash
npm run tauri dev
```

仅启动浏览器中的前端开发服务器：

```bash
npm run dev
```

构建桌面应用：

```bash
npm run tauri build
```

当前开发、构建和运行流程不需要 Python。

## 质量检查

```bash
npm run lint
npm run format:check
npm run test:run
npm run build
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets --all-features -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml --all-targets --all-features
```

## 项目结构

- `src/`：React/TypeScript 界面、前端功能与内置媒体
- `src-tauri/`：Rust 领域逻辑、应用服务、持久化、窗口协调和 Tauri 入口
- `tests/`：跨边界契约测试
- `docs/adr/`：Tauri 迁移和协作流程的架构决策记录
- `.github/workflows/`：Rust、TypeScript 和发布工作流

## 历史版本

Yasumi Clock 1.x 使用 Python、PyQt 和 PyInstaller。`v1.5.1` 是最终 Python 版本；删除旧源码不会删除已经发布的标签或构建产物。

早期版本介绍与截图可在 [Releases](https://github.com/MrXnneHang/Yasumi-Clock/releases) 中查看。

## 感谢贡献者

<a href="https://github.com/GreenHatHG">
  <img src="./fig/conrtibuters/GreenHatHG.png" width="100" height="100" alt="GreenHatHG">
</a>
