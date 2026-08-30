# MiniMax H3 模式切换器 (Mode Switcher)

ComfyUI 自定义节点，将 **Ref2VA（角色参考图）**、**FL2VA（首尾帧）** 和 **混合模式** 整合到一个节点中，通过下拉菜单一键切换，输出统一的 `positive (CONDITIONING)` + `LATENT`。

## 功能特点

- **三种模式一键切换**：
  - `Ref2VA (角色参考图)`：用参考图锁定角色身份，适合开场/锚点段
  - `FL2VA (首尾帧)`：用首帧/尾帧控制画面起止，适合衔接段
  - `混合 (参考图+首尾帧)`：同时使用，角色一致性最强 + 画面控制最精准

- **核心逻辑复用官方实现**：基于 ComfyUI 官方 `comfy_extras/nodes_minimax_h3.py` 的辅助函数，行为与官方节点完全一致

- **输入校验**：自动检测当前模式下缺少必要输入并给出友好报错

- **支持最多4张角色参考图**：对应 `<Picture 1>` ~ `<Picture 4>`

## 安装方法

### 方法一：手动安装
1. 将 `MiniMaxH3_ModeSwitcher` 文件夹复制到 ComfyUI 的 `custom_nodes/` 目录下
2. 重启 ComfyUI
3. 在节点搜索框输入 `MiniMax H3 模式切换器` 或 `ModeSwitcher` 即可找到

### 方法二：ComfyUI Manager
1. 打开 ComfyUI Manager
2. 选择 Install via Git URL
3. 粘贴本仓库地址（如果已上传到 Git）
4. 重启 ComfyUI

## 前置要求

- ComfyUI 版本 >= 0.3.0（需包含官方 MiniMax H3 节点支持）
- 已下载 MiniMax H3 模型（ref2va 和/或 fl2va）
- 已安装 TE-Speed-MiniMaxH3-OSS 插件（可选，用于加速）

## 节点输入说明

### 必需输入

| 输入名 | 类型 | 说明 |
|--------|------|------|
| mode | COMBO | 模式选择：Ref2VA / FL2VA / 混合 |
| clip | CLIP | Qwen3-VL 文本编码器 |
| vae | VAE | 视频 VAE |
| audio_vae | VAE | 音频 VAE |
| prompt | STRING | 提示词（Ref2VA/混合模式用 `<Picture N>` 引用参考图） |
| width | INT | 视频宽度（32的倍数） |
| height | INT | 视频高度（32的倍数） |
| length | INT | 帧数（17k+5格式，如124≈5s, 244≈10s） |

### 可选输入（Ref2VA / 混合模式）

| 输入名 | 类型 | 说明 |
|--------|------|------|
| ref_image_0 | IMAGE | 角色参考图1（`<Picture 1>`） |
| ref_image_1 | IMAGE | 角色参考图2（`<Picture 2>`） |
| ref_image_2 | IMAGE | 角色参考图3（`<Picture 3>`） |
| ref_image_3 | IMAGE | 角色参考图4（`<Picture 4>`） |
| ref_image_size | COMBO | 参考图尺寸：match（快）/ max（身份锁定强） |

### 可选输入（FL2VA / 混合模式）

| 输入名 | 类型 | 说明 |
|--------|------|------|
| first_frame | IMAGE | 首帧图片（建议=上一段最后一帧） |
| last_frame | IMAGE | 尾帧图片（可选，控制结束画面） |

## 输出

| 输出名 | 类型 | 说明 |
|--------|------|------|
| positive | CONDITIONING | 正向条件（连接到 BasicGuider） |
| LATENT | LATENT | 初始 latent（连接到 SamplerCustomAdvanced） |

## 使用示例

### 长视频批量生成工作流

```
角色参考图 ──┐
首帧图 ──────┤
             ▼
    ┌─────────────────────┐
    │ MiniMax H3 模式切换器 │
    │  mode: 混合           │
    └─────────┬───────────┘
              │ positive ──→ BasicGuider ──→ SamplerCustomAdvanced
              │ LATENT ────→ SamplerCustomAdvanced
              ▼
         TE-Speed 加速节点 ──→ BasicScheduler
```

### 模式选择建议

| 场景 | 推荐模式 | 原因 |
|------|----------|------|
| 第1段（开场） | Ref2VA 或 混合 | 用角色参考图锁定身份 |
| 第2~5段（衔接） | FL2VA | 首尾帧保证画面连贯，速度快 |
| 每5段锚点校正 | 混合 | 参考图校正角色漂移 + 首帧保证衔接 |
| 角色特写镜头 | Ref2VA | 身份锁定最重要 |
| 大场景运镜 | FL2VA | 画面控制最重要 |
| 多人对话场景 | 混合 | 既要角色一致又要画面衔接 |

## 提示词技巧

### Ref2VA / 混合模式
用 `<Picture N>` 标签引用参考图，N 从1开始：
```
<Picture 1>的男人和<Picture 2>的女人在咖啡馆对话。
<Picture 1>说：今天天气真好。
环境音：爵士乐、杯碟碰撞声。
```

### FL2VA 模式
不需要 `<Picture N>` 标签，直接描述动作：
```
镜头缓慢推进，男人微笑着说话，女人专注倾听。
背景是暖色调的咖啡馆。
```

## 常见问题

**Q: 报错 "无法导入官方 MiniMax H3 辅助函数"**
A: 请更新 ComfyUI 到最新版本，确保 `comfy_extras/nodes_minimax_h3.py` 存在。

**Q: 报错 "需要至少连接一张参考图"**
A: 当前模式是 Ref2VA 或混合，但没有连接任何 ref_image。请连接参考图，或切换到 FL2VA 模式。

**Q: 混合模式下角色还是会漂移？**
A: 请确保 ref_image_size 设为 `max`（2048短边），并在提示词中重复描述角色外貌。

**Q: 这个节点和官方 MiniMaxH3ReferenceToVideo / MiniMaxH3ImageToVideo 有什么区别？**
A: 核心逻辑完全一致（复用官方辅助函数），区别是：
1. 三种模式整合到一个节点，不用在画布上放两个节点
2. 支持混合模式（同时使用参考图和首尾帧）
3. 输入校验更友好

## 版本历史

- v1.0.0：初始版本，支持 Ref2VA / FL2VA / 混合三种模式
