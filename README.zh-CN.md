# Mixxx API Bridge

[![CI](https://github.com/alexyyyander/mixxx-api-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/alexyyyander/mixxx-api-bridge/actions/workflows/ci.yml)

[English](README.md) | 简体中文

`mixxx-api-bridge` 是一个与 Mixxx 源码兼容的 sidecar 服务，不修改
Mixxx 二进制文件。安装程序会把一份遵循 Mixxx 官方风格的 MIDI 控制器映射
放入用户映射目录；sidecar 通过虚拟 MIDI 端口发送 SysEx 命令，并接收确认和
状态反馈。

## 为什么需要这个 Bridge

MCP Server 或其他面向 AI 的客户端擅长理解意图和编排工作流，但不应该同时
承担与 DJ 引擎交互的底层契约。这个 Bridge 将职责清晰分离：

- **AI/MCP 客户端负责意图**——自然语言命令、Set 规划和多步骤编排可以随时替换。
- **Bridge 负责执行**——把稳定的 HTTP 请求转换成 Mixxx 控制命令，并提供请求 ID、
  真实映射握手、确认、状态反馈和能力发现。
- **Mixxx 负责实时音频**——sidecar 使用受支持的控制器映射 API，不修补音频引擎，
  也不向其中注入代码。

这种职责分离是本项目的核心价值。外部维护的 MCP Server 可以成为第一个客户端，
却不会成为引擎集成的依赖。其他 MCP Server、模型、桌面 UI 或自动化服务都能复用
同一套 API。同样，只要某个 Mixxx 衍生引擎保留控制器脚本 API，就能接入 Bridge，
而不必继承 AI 层。

与 fire-and-forget 控制相比，Bridge 能区分三种状态：Mixxx 进程正在运行、MIDI
传输可用，以及预期映射已经真正回复 `READY`。客户端可以继续等待 `ACK` 和匹配的
反馈，而不是把“数据包已发送”误认为“控制已经生效”。

## 当前范围

- 在 `127.0.0.1:11120` 提供本地 HTTP API。
- 只读的 Mixxx 进程发现（`ps` + macOS `Info.plist`）。
- 通用原始 `group` + `key` 控制，以及常用 Deck/FX 语义别名。
- 支持 hello/ready、set、get、action、subscribe、ack 和 feedback 的 MIDI SysEx 协议。
- 除连续值写入外，还支持通用瞬时动作（`trigger`、`toggle`、`reset`）。
- 可选 Mido/python-rtmidi 后端，以及用于测试的确定性内存后端。
- 为 python-rtmidi 不安全的宿主提供 macOS CoreMIDI C helper 传输。
- macOS 上的原生 CoreMIDI 访问默认关闭，因为部分沙箱宿主可能导致
  python-rtmidi 直接中止解释器。仅在确认宿主可以访问 MIDI 后设置
  `MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1`。
- 不修改 Mixxx C++/源码，也不使用 UI 自动化。

## 安装映射

安装程序只把两个映射文件复制到用户映射目录，不会写入 `Mixxx.app`：

```bash
python scripts/install_mapping.py
# 等价的模块调用方式
python -m mixxx_api_bridge.mapping_installer
# 或在 pip 安装后执行
mixxx-api-bridge-install-mapping
```

在 macOS 上，如果 Mixxx 沙箱数据目录存在，默认目标为
`~/Library/Containers/org.mixxx.mixxx/Data/Library/Application Support/Mixxx/controllers/`；
否则使用 `~/Library/Application Support/Mixxx/controllers/`。复制完成后，在
Mixxx 的 Controllers 设置中启用 **Mixxx API Bridge**。

## 运行 Bridge

存在真实或虚拟 MIDI 端口时，安装 MIDI 支持：

```bash
python -m pip install -e '.[midi]'
mixxx-api-bridge ports
mixxx-api-bridge check --midi-output 'IAC Driver Bus 1' \
  --midi-input 'IAC Driver Bus 1'
mixxx-api-bridge serve --midi-output 'IAC Driver Bus 1' \
  --midi-input 'IAC Driver Bus 1'
```

在 macOS 上，为这些命令显式启用原生后端：

```bash
MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1 mixxx-api-bridge ports
```

如果宿主无法创建 CoreMIDI 客户端，默认会安全返回结构化的
`backend: "disabled"`，而不是弹出原生崩溃窗口。

针对上述 macOS 沙箱情况，可以让一个小型 helper 独立持有 CoreMIDI 虚拟端点，
避免在 Python 中加载 `python-rtmidi`。在仓库目录中编译一次：

```bash
clang -Wall -Wextra -Werror tools/coremidi_virtual_bridge.c \
  -framework CoreMIDI -framework CoreFoundation \
  -o /private/tmp/mixxx-coremidi-bridge
```

使用 helper 启动 sidecar。默认端点名称已经过选择，使 Mixxx 能正确配对输入和输出：

```bash
mixxx-api-bridge serve \
  --coremidi-helper /private/tmp/mixxx-coremidi-bridge
```

在此模式下，可以用 `--midi-output` 和 `--midi-input` 覆盖 helper 的源端与目标端
名称。helper 是独立子进程，会在 sidecar 退出时自动关闭。

相同配置也可以通过 `MIXXX_API_HOST`、`MIXXX_API_PORT`、
`MIXXX_MIDI_OUTPUT`、`MIXXX_MIDI_INPUT` 和 `MIXXX_API_TOKEN` 提供。
如果配置了 token，客户端必须发送 `Authorization: Bearer <token>`。

不连接 MIDI 时，可以运行仅 API 的冒烟测试：

```bash
mixxx-api-bridge serve --dry-run
curl http://127.0.0.1:11120/api/health
curl http://127.0.0.1:11120/api/capabilities
curl -X POST http://127.0.0.1:11120/api/control \
  -H 'Content-Type: application/json' \
  -d '{"path":"decks/1/volume","value":0.75}'

# 瞬时动作和二元控制
curl -X POST http://127.0.0.1:11120/api/action \
  -H 'Content-Type: application/json' \
  -d '{"action":"toggle","path":"decks/1/play","wait_ms":500}'

curl -X POST http://127.0.0.1:11120/api/action \
  -H 'Content-Type: application/json' \
  -d '{"action":"trigger","group":"[Channel1]","key":"beatloop_4_activate"}'
```

dry-run 模式可以验证 HTTP 和协议层，但没有连接 MIDI 端口，因此不能修改 Mixxx
控制项。

## 端到端验证

2026-09-01，CoreMIDI C helper 路径已在本机使用 Mixxx 2.5.6 完成验证。
实时健康检查返回了 `transport: "coremidi-c"`、`bridge.connected: true`、
已加载的 `MixxxApiBridge` 映射，以及远端映射能力。

下面的非干扰性控制闭环会先读取位于中央的 crossfader（`0.5`），再把同一个值写回：

```bash
BRIDGE_URL=http://127.0.0.1:11120

curl "$BRIDGE_URL/api/control?path=mixer%2Fcrossfader&wait_ms=1000"

curl -X POST "$BRIDGE_URL/api/control" \
  -H 'Content-Type: application/json' \
  -d '{"path":"mixer/crossfader","value":0.5,"wait_ms":1000}'
```

写请求返回了 `accepted: true`、`connected: true`、一个 `ACK` 和一个 feedback
帧。ACK 与 feedback 使用相同的 request ID 和值，证明完整的
HTTP → SysEx → Mixxx mapping → SysEx → HTTP 路径已经打通。先读取当前值再写回
相同值，可以把它作为在线系统的安全、无操作冒烟测试。

## API 示例

完整端点和协议文档见 [`docs/API.md`](docs/API.md) 与
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)，安装细节见
[`docs/INSTALL.md`](docs/INSTALL.md)。

## 仓库结构

- `src/mixxx_api_bridge/`：sidecar 包、协议、传输、HTTP Server、进程发现和控制注册表。
- `src/mixxx_api_bridge/mapping/`：安装到 Mixxx 用户控制器目录的 XML/JavaScript 映射。
- `tests/`：Python、协议、mapping runtime 和打包测试。
- `.github/workflows/ci.yml`：macOS/Linux 测试和发行检查。
- `CONTRIBUTING.md`、`SECURITY.md` 和 `CHANGELOG.md`：GitHub 项目策略。

使用语义别名：

```json
{"path":"fx/units/1/mix","value":0.5}
```

或者直接访问任意可写 Mixxx ControlObject：

```json
{
  "group":"[EffectRack1_EffectUnit1_Effect1]",
  "key":"parameter1",
  "value":0.65,
  "scale":"normalized"
}
```

`normalized` 值始终位于 0..1 范围内，并通过 `engine.setParameter` 应用。
只有在已知控制项原生取值范围时才使用 `raw`。效果参数名称是动态的；在 mapping
元数据表能够把 `time` 或 `feedback` 等名称映射到参数槽之前，请使用 `parameterN`。

原始形式可以访问当前 Mixxx 版本向控制器映射公开的任何 ControlObject。它不能让
只读控制项变为可写、不能枚举完整控制索引，也不能取代动作专用 API。瞬时按钮请使用
`/api/action`，只读 mapping 设置请使用 `/api/setting`；sidecar 不会修改 Mixxx
全局偏好设置。

随附映射声明了只读的 `triggerDelayMs` 设置，用于控制瞬时 trigger 动作的持续时间。
启用其他声明了设置项的映射后，也可以读取对应设置。

## 协议握手

Bridge 启动时会发送 `HELLO` SysEx 帧，映射收到后回复 `READY`。这比单纯检查
进程或 MIDI 端口是否存在更可靠。`GET /api/status` 会同时报告进程发现和握手状态。

Bridge 还支持 capabilities 帧，客户端可以据此确认已加载映射是否理解
`set`、`get`、`subscribe` 和 feedback 操作。

## 开发

```bash
python -m pytest -q
python -m compileall src scripts
```
