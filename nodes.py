"""
MiniMax H3 模式切换器自定义节点
================================
整合 Ref2VA（角色参考图）、FL2VA（首尾帧）和混合模式，
通过下拉菜单一键切换，输出统一的 CONDITIONING + LATENT。

核心逻辑复用 ComfyUI 官方 MiniMax H3 节点的辅助函数，
确保与官方节点行为完全一致。
"""
import math
import node_helpers
import comfy.sd
import folder_paths

# 复用官方 MiniMax H3 节点的辅助函数和常量
try:
    from comfy_extras.nodes_minimax_h3 import (
        _empty_av_latent,
        _resize,
        adapt_canvas,
        CANVAS_MULTIPLE,
        REF_IMAGE_SHORT_EDGE,
        FPS,
    )
    OFFICIAL_HELPERS_AVAILABLE = True
except ImportError:
    OFFICIAL_HELPERS_AVAILABLE = False
    _empty_av_latent = None
    _resize = None
    adapt_canvas = None
    CANVAS_MULTIPLE = 32
    REF_IMAGE_SHORT_EDGE = 2048
    FPS = 24


class MiniMaxH3ModeSwitcher:
    """
    MiniMax H3 模式切换器
    三种模式：
      - Ref2VA (角色参考图)：用参考图锁定角色身份，适合开场/锚点段
      - FL2VA (首尾帧)：用首帧/尾帧控制画面起止，适合衔接段
      - 混合 (参考图+首尾帧)：同时使用，角色一致性最强 + 画面控制最精准
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": ([
                    "Ref2VA (角色参考图)",
                    "FL2VA (首尾帧)",
                    "混合 (参考图+首尾帧)",
                ], {
                    "default": "Ref2VA (角色参考图)",
                    "tooltip": "选择条件构建模式。\n"
                               "Ref2VA：用参考图锁定角色身份，适合开场/锚点段。\n"
                               "FL2VA：用首帧/尾帧控制画面起止，适合衔接段。\n"
                               "混合：同时使用参考图和首尾帧，角色一致性最强。"
                }),
                "ref2va_model": (folder_paths.get_filename_list("diffusion_models"), {
                    "tooltip": "Ref2VA / 混合模式使用的 UNET 模型。\n切换到 Ref2VA 或混合模式时自动加载此模型。"
                }),
                "fl2va_model": (folder_paths.get_filename_list("diffusion_models"), {
                    "tooltip": "FL2VA 模式使用的 UNET 模型。\n切换到 FL2VA 模式时自动加载此模型。"
                }),
                "weight_dtype": (["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"], {
                    "default": "default",
                    "tooltip": "模型权重精度。default=自动，fp8=省显存（需显卡支持）。"
                }),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "audio_vae": ("VAE",),
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "dynamicPrompts": True,
                    "tooltip": "描述镜头、动作、对白和音效。Ref2VA/混合模式下用 <Picture 1>、<Picture 2> 引用参考图。"
                }),
                "width": ("INT", {
                    "default": 1344, "min": 256, "max": 2048, "step": 32,
                    "tooltip": "视频宽度，需为32的倍数。H3原生短边768px。"
                }),
                "height": ("INT", {
                    "default": 768, "min": 256, "max": 2048, "step": 32,
                    "tooltip": "视频高度，需为32的倍数。"
                }),
                "length": ("INT", {
                    "default": 124, "min": 5, "max": 3600, "step": 17,
                    "tooltip": "帧数（24fps）。124≈5s，244≈10s，362≈15s。需满足 17k+5 格式。"
                }),
            },
            "optional": {
                # ===== Ref2VA / 混合模式专用（最多9张，与官方节点对齐）=====
                "ref_image_0": ("IMAGE", {
                    "tooltip": "角色参考图1（对应 <Picture 1>）。Ref2VA/混合模式必填。"
                }),
                "ref_image_1": ("IMAGE", {
                    "tooltip": "角色参考图2（对应 <Picture 2>）。可选。"
                }),
                "ref_image_2": ("IMAGE", {
                    "tooltip": "角色参考图3（对应 <Picture 3>）。可选。"
                }),
                "ref_image_3": ("IMAGE", {
                    "tooltip": "角色参考图4（对应 <Picture 4>）。可选。"
                }),
                "ref_image_4": ("IMAGE", {
                    "tooltip": "角色参考图5（对应 <Picture 5>）。可选。"
                }),
                "ref_image_5": ("IMAGE", {
                    "tooltip": "角色参考图6（对应 <Picture 6>）。可选。"
                }),
                "ref_image_6": ("IMAGE", {
                    "tooltip": "角色参考图7（对应 <Picture 7>）。可选。"
                }),
                "ref_image_7": ("IMAGE", {
                    "tooltip": "角色参考图8（对应 <Picture 8>）。可选。"
                }),
                "ref_image_8": ("IMAGE", {
                    "tooltip": "角色参考图9（对应 <Picture 9>）。可选。"
                }),
                "ref_image_size": (["match", "max"], {
                    "default": "match",
                    "tooltip": "参考图尺寸。match=缩放到生成分辨率（快）；max=保持2048短边（身份锁定更强，慢）。"
                }),
                # ===== FL2VA / 混合模式专用 =====
                "first_frame": ("IMAGE", {
                    "tooltip": "首帧图片。FL2VA/混合模式建议填写，等于上一段最后一帧。"
                }),
                "last_frame": ("IMAGE", {
                    "tooltip": "尾帧图片（可选）。用于精准控制结束画面。"
                }),
            }
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "LATENT")
    RETURN_NAMES = ("MODEL", "positive", "LATENT")
    FUNCTION = "encode"
    CATEGORY = "MiniMax H3"

    def encode(self, mode, ref2va_model, fl2va_model, weight_dtype, clip, vae, audio_vae, prompt, width, height, length,
               ref_image_0=None, ref_image_1=None, ref_image_2=None, ref_image_3=None,
               ref_image_4=None, ref_image_5=None, ref_image_6=None, ref_image_7=None,
               ref_image_8=None,
               ref_image_size="match", first_frame=None, last_frame=None):

        if not OFFICIAL_HELPERS_AVAILABLE:
            raise RuntimeError(
                "无法导入官方 MiniMax H3 辅助函数。请更新 ComfyUI 到最新版本 "
                "(需要包含 comfy_extras/nodes_minimax_h3.py)。"
            )

        # ===== 根据 mode 自动加载对应 UNET 模型 =====
        # FL2VA 模式用 fl2va 模型，Ref2VA 和混合模式用 ref2va 模型
        if "FL2VA" in mode and "混合" not in mode:
            model_name = fl2va_model
            model_kind = "FL2VA"
        else:
            model_name = ref2va_model
            model_kind = "Ref2VA"

        if not model_name:
            raise ValueError(
                f"当前模式为「{mode}」，但未选择对应的 UNET 模型。\n"
                f"请在节点的 {model_kind}_model 下拉菜单中选择模型文件。"
            )

        print(f"[MiniMaxH3ModeSwitcher] 模式={mode}，加载 {model_kind} 模型: {model_name}")
        model = comfy.sd.load_unet(model_name, weight_dtype)

        # 判断当前模式启用哪些分支
        use_ref2va = "Ref2VA" in mode or "混合" in mode
        use_fl2va = "FL2VA" in mode or "混合" in mode

        # 模式输入校验
        all_ref_images = [ref_image_0, ref_image_1, ref_image_2, ref_image_3,
                          ref_image_4, ref_image_5, ref_image_6, ref_image_7, ref_image_8]
        if use_ref2va and all(img is None for img in all_ref_images):
            raise ValueError(
                f"当前模式为「{mode}」，需要至少连接一张参考图（ref_image_0 ~ ref_image_8）。\n"
                f"如果只想用首尾帧，请切换到「FL2VA (首尾帧)」模式。"
            )
        if use_fl2va and first_frame is None and last_frame is None and "混合" not in mode:
            print(f"[MiniMaxH3ModeSwitcher] 警告：FL2VA 模式未连接首帧/尾帧，将以文生视频模式运行。")

        # 创建空的音视频 latent
        latent, frame_count = _empty_av_latent(width, height, length)

        images = []       # 用于 tokenizer 的关键帧图片
        keyframes = []    # FL2VA 关键帧
        ref_items = []     # Ref2VA 参考项（用于 tokenizer）
        ref_blocks = []    # Ref2VA 参考块（用于 DiT payload）
        payload = {}

        # ========== FL2VA 分支：首尾帧 ==========
        if use_fl2va:
            if first_frame is not None:
                # 首帧：拉伸到画布尺寸（几何锚点）
                img = _resize(first_frame[:1], width, height, "disabled")
                images.append(img)
                keyframes.append({"resolved_frame_index": 0, "image": img})

            if last_frame is not None:
                # 尾帧：保持宽高比居中裁剪
                img = _resize(last_frame[:1], width, height, "center")
                images.append(img)
                keyframes.append({"resolved_frame_index": frame_count - 1, "image": img})

        # ========== Ref2VA 分支：角色参考图 ==========
        if use_ref2va:
            ref_images_list = [img for img in all_ref_images if img is not None]

            for img in ref_images_list:
                h, w = img.shape[1], img.shape[2]

                # 计算缩放比例
                if ref_image_size == "match":
                    scale = min(1.0, math.sqrt((width * height) / (w * h)))
                else:
                    scale = min(1.0, REF_IMAGE_SHORT_EDGE / min(w, h))

                # 对齐到 CANVAS_MULTIPLE（32）
                tw = max(CANVAS_MULTIPLE, round(w * scale / CANVAS_MULTIPLE) * CANVAS_MULTIPLE)
                th = max(CANVAS_MULTIPLE, round(h * scale / CANVAS_MULTIPLE) * CANVAS_MULTIPLE)

                # 缩放并编码
                resized = _resize(img[:1], tw, th, "disabled")
                z = vae.encode(resized)

                ref_items.append({"type": "image", "data": resized})
                ref_blocks.append({
                    "kind": "image",
                    "latent_h": th // 16,
                    "latent_w": tw // 16,
                    "latent": z
                })

        # ========== 分词 + 编码（关键帧和参考图一起处理）==========
        tokens = clip.tokenize(prompt, images=images, minimax_ref_items=ref_items)
        cond = clip.encode_from_tokens_scheduled(tokens)

        # 注入关键帧和参考图到 conditioning payload
        if keyframes:
            for kf in keyframes:
                kf["latent"] = vae.encode(kf.pop("image"))
            payload["minimax_keyframes"] = keyframes

        if ref_blocks:
            payload["minimax_refs"] = ref_blocks

        if payload:
            cond = node_helpers.conditioning_set_values(cond, payload)

        return (model, cond, latent)


# ============================================================
# 节点注册
# ============================================================
NODE_CLASS_MAPPINGS = {
    "MiniMaxH3ModeSwitcher": MiniMaxH3ModeSwitcher,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3ModeSwitcher": "MiniMax H3 模式切换器 (Ref2VA/FL2VA/混合)",
}
