# MiniMax H3 模式切换器 (Mode Switcher)

ComfyUI 自定义节点，将 **Ref2VA（角色参考图）**、**FL2VA（首尾帧）** 和 **混合模式** 整合到一个节点中，通过下拉菜单一键切换，同时**自动加载对应 UNET 模型**，无需手动切换模型。输出统一的 `MODEL` + `positive (CONDITIONING)` + `LATENT`。

## 版本历史

- **v4.0.0**：角色图 / 首帧 / 尾帧全部可选，未连接时自动跳过或降级为文生视频运行，不再强制报错。
- **v3.0.0**：集成模型自动加载。节点根据 mode 自动加载 ref2va 或 fl2va 模型并输出 MODEL，工作流中不再需要单独的 UNETLoader 节点。支持最多 9 张角色参考图。
- **v2.0.0**：支持最多 9 张角色参考图（ref_image_0~8），与官方 MiniMaxH3ReferenceToVideo 节点对齐。
- **v1.0.0**：初始版本，支持 Ref2VA / FL2VA / 混合三种模式，4 张角色图。

## 功能特点

- **三种模式一键切换**：
  - `Ref2VA (角色参考图)`：用参考图锁定角色身份，适合开场/锚点段
  - `FL2VA (首尾帧)`：用首帧/尾帧控制画面起止，适合衔接段
  - `混合 (参考图+首尾帧)`：同时使用，角色一致性最强 + 画面控制最精准
- **⭐ 模型自动切换**：节点内置 ref2va_model 和 fl2va_model 两个参数，切换 mode 时自动加载对应模型并输出 MODEL，无需手动修改 UNETLoader
- **核心逻辑复用官方实现**：基于 ComfyUI 官方 `comfy_extras/nodes_minimax_h3.py` 的辅助函数，行为与官方节点完全一致
- **输入校验**：自动检测当前模式下缺少必要输入并给出友好报错
- **支持最多 9 张角色参考图**：对应 `<Picture 1>` ~ `<Picture 9>`

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
- 已下载 MiniMax H3 模型（ref2va 和 fl2va 两套，放在 `models/diffusion_models/` 目录）
- 已安装 TE-Speed-MiniMaxH3-OSS 插件（可选，用于加速）

## 节点输入说明

### 必需输入

| 输入名 | 类型 | 说明 |
|--------|------|------|
| mode | COMBO | 模式选择：Ref2VA / FL2VA / 混合 |
| ref2va_model | COMBO | Ref2VA/混合模式使用的 UNET 模型文件名 |
| fl2va_model | COMBO | FL2VA 模式使用的 UNET 模型文件名 |
| weight_dtype | COMBO | 模型权重精度：default / fp8_e4m3fn / fp8_e5m2 |
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
| ref_image_0 ~ ref_image_8 | IMAGE | 角色参考图1~9（对应 `<Picture 1>` ~ `<Picture 9>`） |
| ref_image_size | COMBO | 参考图尺寸：match（快）/ max（身份锁定强） |

### 可选输入（FL2VA / 混合模式）

| 输入名 | 类型 | 说明 |
|--------|------|------|
| first_frame | IMAGE | 首帧图片（建议=上一段最后一帧） |
| last_frame | IMAGE | 尾帧图片（可选，控制结束画面） |

## 输出

| 输出名 | 类型 | 说明 |
|--------|------|------|
| MODEL | MODEL | 根据 mode 自动加载的 UNET 模型（连接到 TE-Speed 或采样器） |
| positive | CONDITIONING | 正向条件（连接到 BasicGuider） |
| LATENT | LATENT | 初始 latent（连接到 SamplerCustomAdvanced） |

## 使用示例

### 工作流结构（v3 自动模型切换）

```
角色参考图(1~9) ──┐
首帧图 ────────────┤
                    ▼
         ┌──────────────────────────┐
         │ MiniMax H3 模式切换器      │
         │  mode: 混合                │
         │  ref2va_model: xxx.safetensors │
         │  fl2va_model:  xxx.safetensors │
         └──┬──────────┬──────────┬─┘
            │ MODEL    │ positive │ LATENT
            ▼          ▼          ▼
       TE-Speed加速  BasicGuider  SamplerCustomAdvanced
            │          │              ▲
            ▼          ▼              │
       BasicScheduler ────────────────┘
```

### 模式选择建议

| 场景 | 推荐模式 | 自动加载模型 | 原因 |
|------|----------|-------------|------|
| 第1段（开场） | Ref2VA 或 混合 | ref2va | 用角色参考图锁定身份 |
| 第2~5段（衔接） | FL2VA | fl2va | 首尾帧保证画面连贯，速度快 |
| 每5段锚点校正 | 混合 | ref2va | 参考图校正角色漂移 + 首帧保证衔接 |
| 角色特写镜头 | Ref2VA | ref2va | 身份锁定最重要 |
| 大场景运镜 | FL2VA | fl2va | 画面控制最重要 |
| 多人对话场景 | 混合 | ref2va | 既要角色一致又要画面衔接 |

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

**Q: 切换 mode 后模型会自动切换吗？**
A: 是的。节点根据 mode 自动选择 ref2va_model 或 fl2va_model，并调用 `comfy.sd.load_unet` 加载。ComfyUI 有模型缓存机制，首次加载后切换秒级完成。

**Q: 报错 "无法导入官方 MiniMax H3 辅助函数"**
A: 请更新 ComfyUI 到最新版本，确保 `comfy_extras/nodes_minimax_h3.py` 存在。

**Q: 角色图 / 尾帧不选择图片能否运行？**
A: 可以（v4 起）。所有图片输入（角色图 ref_image_0~8、首帧、尾帧）均为可选：未连接时自动跳过，或降级为文生视频运行（控制台打印警告，不中断）。不用的图片节点请右键 → Mute（禁用）或直接删除 / 断开连线即可。

**Q: 报错 "未选择对应的 UNET 模型"**
A: 当前模式下对应的模型参数为空。请在节点的 ref2va_model 或 fl2va_model 下拉菜单中选择模型文件。

**Q: 混合模式下角色还是会漂移？**
A: 请确保 ref_image_size 设为 `max`（2048短边），并在提示词中重复描述角色外貌。

**Q: 这个节点和官方 MiniMaxH3ReferenceToVideo / MiniMaxH3ImageToVideo 有什么区别？**
A: 核心逻辑完全一致（复用官方辅助函数），区别是：
1. 三种模式整合到一个节点，不用在画布上放两个节点
2. 支持混合模式（同时使用参考图和首尾帧）
3. **自动加载对应模型**，无需手动切换 UNETLoader
4. 支持最多 9 张角色参考图
5. 输入校验更友好
