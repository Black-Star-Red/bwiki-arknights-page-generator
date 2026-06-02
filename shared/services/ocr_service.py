from __future__ import annotations
import re
import cv2
import numpy as np
import os

# CPU 推理默认会走 OneDNN/MKLDNN，部分环境下与 PIR 不兼容会报：
# ConvertPirAttribute2RuntimeAttribute not support [...] onednn_instruction.cc
# 须在 import paddleocr 之前关闭（PaddleX 在导入时读取该变量）
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

from paddleocr import PaddleOCR


def ocr_specialization(photo_path: str, roi_tune=None):
    from core.script_logging import log_info, log_warning
    try:
        import cv2
        import pytesseract
        import numpy as np
        import re
    except ImportError:
        log_warning("OCR依赖缺失，专精识别降级为空 path=%s", photo_path)
        return ""

    # ROI 可调参数（支持通过 roi_tune 覆盖，便于后续 GUI 做滑杆调参）
    cfg = {
        "x1_ratio": 0.00,
        "x2_ratio": 0.45,
        "y1_ratio": 0.25,
        "y2_ratio": 0.75,
        "win_h_ratio": 0.08,
        "win_w_ratio": 0.85,
        "step_ratio": 0.35,
        "pad_x_ratio": 0.01,
        "pad_y_ratio": 0.01,
        "crop_left_bias": 100,
        "crop_top_bias": 10,
        "crop_right_bias": -10,
        "crop_bottom_bias": -20,
    }
    if isinstance(roi_tune, dict):
        cfg.update(roi_tune)

    img_path = photo_path
    try:
        with open(img_path, "rb") as f:
            data = f.read()
    except OSError as e:
        log_warning("OCR读取图片失败，专精识别降级为空 path=%s err=%s", photo_path, e)
        return ""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    log_info("ocr_decode path=%s is_none=%s shape=%s", photo_path, img is None, None if img is None else img.shape)
    if img is None:
        log_warning("OCR图片解码失败，专精识别降级为空 path=%s", photo_path)
        return ""

    H, W = img.shape[:2]
    lang = "chi_sim"
    def norm(s: str) -> str:
        return re.sub(r"\s+", "", s)
    # 只在左侧面板区域粗扫（比例可调）
    x1 = int(W * cfg["x1_ratio"])
    x2 = int(W * cfg["x2_ratio"])
    y1 = int(H * cfg["y1_ratio"])
    y2 = int(H * cfg["y2_ratio"])
    # 防御性裁剪，避免 ROI 参数异常导致空切片
    x1 = max(0, min(x1, W - 1))
    x2 = max(x1 + 1, min(x2, W))
    y1 = max(0, min(y1, H - 1))
    y2 = max(y1 + 1, min(y2, H))
    panel = img[y1:y2, x1:x2]
    # OCR的白名单会让它更“敢只猜这些字”，但也可能降低识别率：我们先用白名单找得分最高
    whitelist = "专精+-0123456789"
    # config_scan = f"--oem 3 --psm 6 -c tessedit_char_whitelist={whitelist}"
    config_scan = "--oem 3 --psm 11"
    def preprocess_for_ocr(bgr):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        # 放大让“小字”更容易被识别
        gray = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        # 轻微去噪 + OTSU（二值化比 adaptive 更稳一些）
        gray = cv2.bilateralFilter(gray, 5, 50, 50)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if th.mean() < 127:
            th = 255 - th
        return th

    best = None
    best_score = -1

    # 滑窗参数（窗口越大越容易包含“专精”，越小越容易漏：先从中等开始）
    win_h = max(1, int(panel.shape[0] * cfg["win_h_ratio"]))
    win_w = max(1, int(panel.shape[1] * cfg["win_w_ratio"]))  # 宽度给够，避免切断一行
    step = max(1, int(win_h * cfg["step_ratio"]))

    for y in range(0, panel.shape[0] - win_h + 1, step):
        roi = panel[y:y + win_h, 0:win_w]
        th = preprocess_for_ocr(roi)

        text = pytesseract.image_to_string(th, lang=lang, config=config_scan)
        t_raw = text.replace(" ", "").replace("\n", "")
        t = norm(text)

        score = 0
        if "专精" in t:
            log_info("ocr_scan_hit text=%s", t)
            score += 10
        score += t.count("专")
        score += t.count("精")
        if t.startswith("专精"):
            score += 10
        if score > best_score:
            best_score = score
            best = (x1, y1 + y, x1 + win_w, y1 + y + win_h, t)

    if best is None or best_score <= 0:
        log_warning("OCR粗扫未命中 path=%s best_score=%s", photo_path, best_score)
        return ""

    bx1, by1, bx2, by2, coarse_text = best
    log_info("ocr_coarse best_score=%s box=%s text=%s", best_score, (bx1, by1, bx2, by2), coarse_text)

    # 精读：对这个窗口再裁得更“干净”一点（padding 可调）
    pad_x = int((bx2 - bx1) * cfg["pad_x_ratio"])
    pad_y = int((by2 - by1) * cfg["pad_y_ratio"])

    fx1 = max(0, bx1 - pad_x + int(cfg["crop_left_bias"]))
    fy1 = max(0, by1 - pad_y + int(cfg["crop_top_bias"]))
    fx2 = min(W, bx2 + pad_x + int(cfg["crop_right_bias"]))
    fy2 = min(H, by2 + pad_y + int(cfg["crop_bottom_bias"]))
    fx2 = max(fx1 + 1, fx2)
    fy2 = max(fy1 + 1, fy2)

    roi_final = img[fy1:fy2, fx1:fx2]
    th_final = preprocess_for_ocr(roi_final)
    # cv2.imshow("th_final", th_final)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # 精读阶段可以用 psm 7（单行）或 6
    # config_final = f"--oem 3 --psm 6 -c tessedit_char_whitelist={whitelist}"
    config_final = f"--oem 3 --psm 6"
    final_text = pytesseract.image_to_string(th_final, lang=lang, config=config_final).replace(" ", "").replace("\n", "")
    # 置信度输出：使用 image_to_data 的 conf 作为 OCR 质量参考
    conf_score = 0.0
    try:
        data = pytesseract.image_to_data(
            th_final, lang=lang, config=config_final, output_type=pytesseract.Output.DICT
        )
        conf_vals = []
        for c in data.get("conf", []):
            try:
                v = float(c)
                if v >= 0:
                    conf_vals.append(v)
            except (TypeError, ValueError):
                continue
        if conf_vals:
            conf_score = sum(conf_vals) / len(conf_vals)
    except Exception as e:
        log_warning("OCR置信度计算失败 path=%s err=%s", photo_path, e)
    conf_level = "high" if conf_score >= 80 else ("medium" if conf_score >= 60 else "low")
    log_info(
        "ocr_final path=%s box=%s text=%s conf=%.2f conf_level=%s",
        photo_path,
        (fx1, fy1, fx2, fy2),
        final_text,
        conf_score,
        conf_level,
    )
    if conf_level == "low":
        log_warning("OCR置信度偏低 path=%s conf=%.2f text=%s", photo_path, conf_score, final_text)

    def _normalize_keyword_text(s: str) -> str:
        return (
            re.sub(r"\s+", "", s or "")
            .replace("專", "专")
            .replace("精", "精")
            .replace("菁", "精")
            .replace("睛", "精")
        )

    def _has_keyword(s: str) -> bool:
        ns = _normalize_keyword_text(s)
        return ("专精" in ns) or (re.search(r"专.{0,3}精", ns) is not None)
    # 优先用 final_text；若 final 丢字则回退 coarse_text
    final_ok = _has_keyword(final_text)
    coarse_ok = _has_keyword(coarse_text)

    if final_ok:
        log_info("ocr_accept path=%s source=final raw=%s", photo_path, final_text)
        return final_text
    if coarse_ok:
        log_warning(
            "OCR回退到粗识别 path=%s final=%s coarse=%s",
            photo_path,
            final_text,
            coarse_text,
        )
        return coarse_text

    log_warning(
        "OCR结果未包含关键词 path=%s final=%s coarse=%s",
        photo_path,
        final_text,
        coarse_text,
    )
    return ""





def imread_unicode(path: str):
    """Windows 下 cv2.imread 对含中文的路径常返回 None，用 imdecode 可读 Unicode 路径。"""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)
# 默认会加载：文档方向 + UVDoc 矫正 + server 级 det/rec，CPU 上极易“卡死”。
# 游戏立绘截图一般无需文档矫正；mobile 模型在 CPU 上快一个数量级以上。
print("正在加载 OCR 模型（首次会下载/编译，请稍候）…", flush=True)
ocr = PaddleOCR(
    lang="ch",
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)
print("模型加载完成。", flush=True)

# 送入 det 的图像最长边上限（像素）。原先 2× 放大后约 2000×4200，server 模型在 CPU 上极慢。
MAX_OCR_SIDE = 1600

# 宣传图/档案条里常见「橙黄字段名 + 白字内容」。灰度+自适应二值化容易把偏暗的橙黄字吃掉，只留白字。
# 需要强二值化（例如极糊截图）时再改为 True。
USE_ADAPTIVE_BINARIZE = False


def preprocess(img):
    """缩放 + 可选轻去噪；默认保留 BGR 颜色，避免橙/黄标签在二值化里消失。"""
    bgr = img
    h, w = bgr.shape[:2]
    side = max(h, w)
    if side > MAX_OCR_SIDE:
        scale = MAX_OCR_SIDE / side
        bgr = cv2.resize(
            bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
        )
    elif side < 800:
        bgr = cv2.resize(bgr, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

    if USE_ADAPTIVE_BINARIZE:
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        g = cv2.bilateralFilter(g, 7, 50, 50)
        return cv2.adaptiveThreshold(
            g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 8
        )
    return cv2.bilateralFilter(bgr, 5, 40, 40)

def to_bgr3(img: np.ndarray) -> np.ndarray:
    """PaddleOCR 流水线需要 H×W×3 的 BGR；预处理后的二值图只有 H×W。"""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.ndim == 3 and img.shape[2] == 1:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def run_ocr(img):
    # PaddleOCR 3.x：用 predict；行方向分类由构造参数 use_textline_orientation 控制（本脚本已关闭）
    out = ocr.predict(to_bgr3(img))
    if not out:
        return ""
    res = out[0]
    rec_texts = res.get("rec_texts") or []
    return "\n".join(rec_texts)

def extract_mastery(text: str) -> str | None:
    """取「专精」后的研究方向/技能列表；游戏 UI 与 OCR 常拆成多行，需合并。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # 遇到下一条档案字段标题则停止，避免把后面段落拼进专精
    stop_line = re.compile(
        r"^(精英化|等级|职业|分支|标签|综合体检测|初始开放|基建技能|特性|天赋|招聘合同|"
        r"客观履历|临床诊断|造影检测|矿石病感染情况|体细胞与源石|血液源石结晶密度|"
        r"物理强度|战场机动|生理耐受|战术规划|战斗技巧|后勤技能|源石技艺适应性|"
        r"模组|潜能|再部署|部署费用|阻挡数|攻击范围|初始携带|"
        r"身高|体重|性别|种族|生日|出身|中文CV|中)"
    )
    max_follow = 12

    for i, line in enumerate(lines):
        if "专精" not in line and '、' not in line:
            continue
        chunks: list[str] = []

        same = re.search(r"专精\s*[：:]\s*(.+)$", line)
        temp= False
        if same:
            c = same.group(1).strip()
            if c:
                chunks.append(c)
        elif re.fullmatch(r"专精\s*", line):
            pass
        else:
            tail = re.search(r"专精(.+)$", line)
            if tail:
                c = tail.group(1).strip().lstrip("：:").strip()
                if c:
                    chunks.append(c)
            elif not chunks and "、" in line and "专精" not in line:
                if line.endswith("、"):
                    chunks.append(line[:-1])
                    temp = True
                else:
                    chunks.append(line)

        j = i + 1
        n = 0
        while j < len(lines) and n < max_follow:
            nxt = lines[j]
            if stop_line.match(nxt) or nxt.isdigit():# or (检测到chunks[-1] 不是“、”结尾 则停止)
                break
            if len(nxt) < 2:
                n += 1
                j += 1
                continue
            if nxt.endswith("、"):
                temp=True
                chunks.append(nxt[:-1])
            else:
                chunks.append(nxt)
            if not nxt.endswith("、") and temp == True:
                break
            n += 1
            j += 1

        if chunks:
            return "、".join(chunks)
    return None
def ocr_exec(img_path: str) -> str:
    img = imread_unicode(img_path)
    if img is None:
        raise FileNotFoundError(
            f"无法读取图片（路径错误或 OpenCV 不支持该路径）: {img_path}"
        )
    h, w = img.shape[:2]

    # 两个区域：全图 + 右侧档案区（这类立绘通常在这里）
    rois = [
        ("full", img),
        ("profile", img[int(h*0.35):int(h*0.75), int(w*0.45):int(w*0.97)])
    ]

    all_text = []
    for name, roi in rois:
        print(f"OCR 区域: {name} …", flush=True)
        txt = run_ocr(preprocess(roi))
        all_text.append(txt)
        print(f"  完成，字符数约 {len(txt)}", flush=True)

    merged = "\n".join(all_text)
    merged = merged.replace(" ", "").replace("　", "")
    print(merged)

    val = extract_mastery(merged)
    if not val:
        m = re.search(r"专精\s*[：:]\s*([^\n【]{1,120})", merged)
        if m:
            val = m.group(1).strip()

    if val:
        print("专精 =", val)
        return val
    else:
        line = next((x for x in merged.splitlines() if "专精" in x), None)
        print("未精确提取，候选行：", line)
        return ""

__all__ = [
    "ocr_exec",
]
