# 线条小狗桌宠：开发上下文

## 项目目标

- Windows 本地桌面宠物，个人使用。
- 当前手动维护版本为 `v0.1.0`；版本号同时体现在 `README.md` 和 `pixi.toml`。
- 不自动修改版本号；发布新版本时人工更新版本号、版本表和发布说明。
- `pixi run build <major> <minor> <patch>` 仅使用传入版本命名产物，例如 `pixi run build 0 1 0` 生成 `dist/v0.1.0-LineDogPet.exe`。
- Python 3.11、PySide6、Pixi 管理环境。
- 窗口透明、无边框、始终置顶，使用 `Qt.Tool` 避免任务栏按钮。
- 保持实现小而清晰，不为简单功能引入复杂框架。

## 当前交互约定

- 支持 `xiaobai`、`xiaojimao`、`together` 三种角色状态。
- 左键短按随机切换到与当前不同的状态。
- 左键拖动窗口；拖动结束不触发状态切换。
- 右键菜单可手动选状态、回到右下角、退出。
- 进入状态时，从该状态目录所有 `*.gif` 中随机选择动画。
- 同状态有多个 GIF 时，尽量避免连续重复上一次文件。
- 无操作 20～60 秒后在当前状态内随机换动作；暂停或隐藏时停止待机换动作。
- Windows 通知区域图标提供显示/隐藏、暂停、换动作、切换状态、提醒开关和退出。
- 桌宠和托盘菜单均提供活动提醒、喝水提醒的即时测试入口。
- 使用 `QSettings` 保存位置、角色状态和提醒开关；无效的跨屏位置不得恢复。
- GIF 每帧的不透明像素生成窗口遮罩，使透明画布区域点击穿透。
- 启动 20 分钟后先提醒“记得站起来活动活动哦”，40 分钟后提醒“记得喝水”，之后每 20 分钟交替，因此每条提醒的周期都是 40 分钟。
- 损坏 GIF 应被跳过；没有可用 GIF 时显示占位内容。
- 运行时窗口固定为 `154×154`（原 `220×220` 的 70%），切换动画时不得改变窗口尺寸或位置。
- GIF 按原始宽高比自动适配到固定画布内，并在底部居中。

## 素材约定

```text
assets/xiaobai/*.gif
assets/xiaojimao/*.gif
assets/together/*.gif
```

- 不使用 `assets/candidates` 中间层。
- GIF 文件名任意，不依赖固定的 `pet.gif`。
- 三个状态当前都至少保留 10 个 GIF。
- 整理后的素材统一为 `220×220` 透明画布；可见内容等比填满一条边并在底部居中。用户自行放入的其他尺寸 GIF 也由运行时代码自动适配。
- 新增或替换 GIF 后运行 `pixi run normalize-assets`；该任务会原地修改素材，处理前应保留原图。
- `assets/SOURCES.md` 保存现有网络素材的页面来源。
- 保留用户已有素材；除非用户明确要求，不自动下载、覆盖或删除素材。

## 代码地图

- `main.py`：QApplication 入口和启动资源检查。
- `pet_controller.py`：托盘图标、QSettings、窗口与调度器协调。
- `pet_scheduler.py`：随机待机计时和交替活动/喝水提醒。
- `pet_window.py`：窗口属性、位置、鼠标和右键菜单。
- `pet_animator.py`：扫描、随机选择、验证并播放 GIF。
- `pet_state.py`：状态枚举和不重复的随机状态选择。
- `utils.py`：源码/PyInstaller 路径解析和素材目录扫描。
- `normalize_assets.py`：统一 GIF 透明画布、视觉尺寸和底部中心锚点。
- `smoke_test.py`：离屏快速运行测试。

## 常用命令

```powershell
pixi run start
pixi run check
pixi run smoke
pixi run normalize-assets
pixi run build 0 1 0
```

- 快速迭代时运行 `check` 和 `smoke`。
- 不要在每次改动后自动执行 `pixi run build`。
- 只有用户明确要求更新 EXE 时才打包；不要自行调用无版本参数的 `pixi run build`。
- `dist` 中的 EXE 可能落后于源码；打包前人工确认 README、`pixi.toml` 和命令参数的版本一致。

## 修改注意事项

- 保持 PyInstaller `_MEIPASS` 资源路径兼容。
- 窗口透明相关标志应在显示窗口前设置。
- 鼠标单击与拖动必须继续通过移动阈值区分。
- 新增功能后优先扩展快速测试，不用打包来验证常规逻辑。
