"""Rastreador visual do LoL — print, classifica, caixa no boneco. Ligado ao coach."""

import ctypes
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf

_COACH = Path(__file__).resolve().parents[1]
if str(_COACH) not in sys.path:
    sys.path.insert(0, str(_COACH))

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "data" / "ml_ability" / "mobilenet.keras"
LABELS_PATH = MODEL_PATH.with_suffix(".labels.npy")
LOG = ROOT / "data" / "ml_ability" / "detect.log"
IMAGE_SIZE = 224
BORDA = 3
WS_POPUP = 0x80000000
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200
SWP_NOSENDCHANGING = 0x0400
SW_SHOWNA = 8
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
WM_DESTROY = 0x0002
WM_QUIT = 0x0012
EX = 0x00080000 | 0x00000020 | 0x00000008 | 0x00000080 | 0x08000000
POS = SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_NOSENDCHANGING
PS_SOLID = 0
DWMWA_EXTENDED_FRAME_BOUNDS = 9

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dwmapi = ctypes.windll.dwmapi
kernel32 = ctypes.windll.kernel32
HANDLE = ctypes.c_void_p
HWND_TOPMOST = HANDLE(-1)
LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t

user32.CreateWindowExW.restype = ctypes.c_void_p
user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_uint,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
]
user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.DestroyWindow.argtypes = [ctypes.c_void_p]
user32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.POINT)]
user32.SetWindowPos.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.IsWindow.argtypes = [ctypes.c_void_p]
user32.IsWindow.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
user32.GetWindowTextW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR, ctypes.c_int]
user32.GetDC.restype = ctypes.c_void_p
user32.GetDC.argtypes = [ctypes.c_void_p]
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.UpdateLayeredWindow.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE),
    ctypes.c_void_p, ctypes.POINTER(wintypes.POINT),
    wintypes.COLORREF, ctypes.c_void_p, ctypes.c_uint,
]
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [HANDLE, ctypes.c_uint, WPARAM, LPARAM]
user32.DrawTextW.argtypes = [HANDLE, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.RECT), ctypes.c_uint]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), HANDLE, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
gdi32.CreateCompatibleDC.restype = HANDLE
gdi32.CreateCompatibleDC.argtypes = [HANDLE]
gdi32.CreateDIBSection.restype = HANDLE
gdi32.CreateDIBSection.argtypes = [
    HANDLE, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), HANDLE, ctypes.c_uint,
]
gdi32.SelectObject.restype = HANDLE
gdi32.SelectObject.argtypes = [HANDLE, HANDLE]
gdi32.DeleteObject.argtypes = [HANDLE]
gdi32.DeleteDC.argtypes = [HANDLE]
gdi32.CreatePen.restype = HANDLE
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.COLORREF]
gdi32.GetStockObject.restype = HANDLE
gdi32.GetStockObject.argtypes = [ctypes.c_int]
gdi32.Rectangle.argtypes = [HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.SetBkMode.argtypes = [HANDLE, ctypes.c_int]
gdi32.SetTextColor.argtypes = [HANDLE, wintypes.COLORREF]
gdi32.BitBlt.argtypes = [
    HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
SRCCOPY = 0x00CC0020
SW_HIDE = 0
dwmapi.DwmGetWindowAttribute.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
]

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    user32.SetProcessDPIAware()

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HANDLE, ctypes.c_uint, WPARAM, LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows.argtypes = [WNDENUMPROC, ctypes.c_void_p]

_model = None
_names = None
_label = [""]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_ushort),
        ("biBitCount", ctypes.c_ushort),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


@WNDPROC
def _wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _title(hwnd):
    n = max(user32.GetWindowTextLengthW(hwnd) + 1, 1)
    buf = ctypes.create_unicode_buffer(n)
    user32.GetWindowTextW(hwnd, buf, n)
    return buf.value


def _cliente(hwnd):
    rc = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    w, h = rc.right - rc.left, rc.bottom - rc.top
    if w >= 800 and h >= 500:
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return pt.x, pt.y, w, h
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        return None
    w, h = r.right - r.left, r.bottom - r.top
    if w < 800 or h < 500:
        return None
    return r.left, r.top, w, h


def _hwnd_lol():
    best = [0, 0]

    @WNDENUMPROC
    def cb(hwnd, _):
        cls, title = _class_name(hwnd), _title(hwnd)
        if cls != "RiotWindowClass" and "League of Legends (TM) Client" not in title:
            return True
        info = _cliente(hwnd)
        if not info:
            return True
        area = info[2] * info[3]
        if area > best[0]:
            best[0] = area
            best[1] = hwnd
        return True

    user32.EnumWindows(cb, None)
    return best[1] or user32.FindWindowW("RiotWindowClass", None)


def _shot(x, y, w, h):
    """Screenshot no mesmo sistema de coordenadas do overlay."""
    hdc = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bits = ctypes.c_void_p()
    hbmp = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    old = gdi32.SelectObject(mem, hbmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, x, y, SRCCOPY)
    buf = np.ctypeslib.as_array((ctypes.c_uint8 * (w * h * 4)).from_address(bits.value))
    bgr = buf.reshape(h, w, 4)[:, :, :3].copy()
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(None, hdc)
    return bgr


def _matar_zumbis():
    while True:
        h = user32.FindWindowW("LolDetectBox", None)
        if not h:
            break
        user32.DestroyWindow(h)


def _pixels(texto, w, h):
    w, h = max(int(w), 20), max(int(h), 20)
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:BORDA, :] = (0, 255, 0, 255)
    img[-BORDA:, :] = (0, 255, 0, 255)
    img[:, :BORDA] = (0, 255, 0, 255)
    img[:, -BORDA:] = (0, 255, 0, 255)
    if texto and h > 22 and w > 40:
        tw = max(w - 2 * BORDA, 8)
        canvas = np.zeros((18, tw, 3), dtype=np.uint8)
        cv2.putText(canvas, texto[:22], (2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
        bgra = np.dstack([canvas, np.where(canvas.any(axis=2), 255, 0).astype(np.uint8)])
        img[BORDA : BORDA + 18, BORDA : BORDA + tw] = bgra
    return np.ascontiguousarray(np.flipud(img))


def _blit(hwnd, x, y, w, h, texto):
    pix = _pixels(texto, w, h)
    hh, ww = pix.shape[:2]
    hdc_scr = user32.GetDC(None)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_scr)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = ww
    bmi.bmiHeader.biHeight = hh
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bits = ctypes.c_void_p()
    hbmp = gdi32.CreateDIBSection(hdc_mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    ctypes.memmove(bits, pix.ctypes.data, pix.nbytes)
    old = gdi32.SelectObject(hdc_mem, hbmp)
    blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
    ok = user32.UpdateLayeredWindow(
        hwnd, hdc_scr,
        ctypes.byref(wintypes.POINT(int(x), int(y))),
        ctypes.byref(wintypes.SIZE(ww, hh)),
        hdc_mem,
        ctypes.byref(wintypes.POINT(0, 0)),
        0, ctypes.byref(blend), ULW_ALPHA,
    )
    gdi32.SelectObject(hdc_mem, old)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(None, hdc_scr)
    return ok


def _banda(hwnd):
    set_band = getattr(user32, "SetWindowBand", None)
    if set_band is None:
        _log("SetWindowBand ausente")
        return
    set_band.argtypes = [HANDLE, HANDLE, ctypes.c_uint]
    set_band.restype = wintypes.BOOL
    for band in (14, 2, 16, 1):
        if set_band(hwnd, None, band):
            _log(f"band {band}")
            return
    _log(f"band falhou {ctypes.GetLastError()}")


def _criar_overlay():
    inst = kernel32.GetModuleHandleW(None)
    name = "LolDetectBox"
    wc = WNDCLASSW()
    wc.lpfnWndProc = _wndproc
    wc.hInstance = inst
    wc.lpszClassName = name
    user32.RegisterClassW(ctypes.byref(wc))
    hwnd = None
    create_band = getattr(user32, "CreateWindowInBand", None)
    if create_band is not None:
        create_band.restype = HANDLE
        create_band.argtypes = [
            ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_uint,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            HANDLE, HANDLE, HANDLE, HANDLE, ctypes.c_uint,
        ]
        for band in (14, 2):
            hwnd = create_band(EX, name, "", WS_POPUP, 0, 0, 64, 64, None, None, inst, None, band)
            if hwnd:
                _log(f"in-band {band}")
                break
    if not hwnd:
        hwnd = user32.CreateWindowExW(EX, name, "", WS_POPUP, 0, 0, 64, 64, None, None, inst, None)
        _log("createex")
    if hwnd:
        user32.ShowWindow(hwnd, SW_SHOWNA)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 64, 64, POS)
        _banda(hwnd)
    return hwnd


def _pump():
    msg = wintypes.MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        if msg.message == WM_QUIT:
            return False
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    return True


def _load():
    global _model, _names
    if _model is None:
        _names = np.load(LABELS_PATH, allow_pickle=True)
        _model = tf.keras.models.load_model(MODEL_PATH)
    return _model, _names


def _perguntar(bgr):
    H, W = bgr.shape[:2]
    campo = bgr[int(H * 0.08) : int(H * 0.76), int(W * 0.06) : int(W * 0.80)]
    if campo.size == 0:
        campo = bgr
    model, names = _load()
    rgb = cv2.cvtColor(campo, cv2.COLOR_BGR2RGB)
    x = tf.image.resize(rgb, [IMAGE_SIZE, IMAGE_SIZE]).numpy() / 255.0
    p = model.predict(np.expand_dims(x, 0), verbose=0)[0]
    i = int(p.argmax())
    return str(names[i]), float(p[i])


def _hp(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    g = cv2.inRange(hsv, (35, 80, 80), (88, 255, 255))
    r = cv2.inRange(hsv, (0, 90, 80), (10, 255, 255)) | cv2.inRange(hsv, (170, 90, 80), (180, 255, 255))
    y = cv2.inRange(hsv, (18, 90, 90), (36, 255, 255))
    return cv2.bitwise_or(cv2.bitwise_or(g, r), y)


def _onde(bgr):
    """Caixa no boneco: embaixo da barra de vida, ou no ponto da câmera travada."""
    H, W = bgr.shape[:2]
    x0, y0 = int(W * 0.06), int(H * 0.08)
    x1, y1 = int(W * 0.80), int(H * 0.76)
    campo = bgr[y0:y1, x0:x1]
    if campo.size:
        m = cv2.morphologyEx(_hp(campo), cv2.MORPH_CLOSE, np.ones((3, 11), np.uint8))
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        barras = []
        ch, cw = campo.shape[:2]
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if not (58 <= w <= 140 and 5 <= h <= 12 and w >= h * 6):
                continue
            if y < 3 or y + h + 3 >= ch:
                continue
            if (_hp(campo[y : y + h, x : x + w]) > 0).mean() < 0.55:
                continue
            if (_hp(campo[y - 3 : y, x : x + w]) > 0).mean() > 0.30:
                continue
            barras.append((x, y, w, h))
        if barras:
            tx, ty = cw // 2, int(ch * 0.55)
            bx, by, bw, bh = min(
                barras, key=lambda b: (b[0] + b[2] // 2 - tx) ** 2 + (b[1] - ty) ** 2
            )
            pad = 5
            cx = max(0, bx - pad)
            cy = min(ch - 1, by + bh + 1)
            cw_ = min(cw - cx, bw + 2 * pad)
            ch_ = min(ch - cy, max(int(bw * 1.45), 70))
            return x0 + cx, y0 + cy, cw_, ch_
    bw, bh = 88, 128
    return W // 2 - bw // 2, int(H * 0.60) - bh // 2, bw, bh


def run():
    LOG.write_text("", encoding="utf-8")
    _log("start")
    _matar_zumbis()
    overlay = _criar_overlay()
    if not overlay:
        _log("overlay falhou")
        return 1
    fixo = None
    votos = []
    caixa = None
    shown = None
    while _pump():
        lol = _hwnd_lol()
        info = _cliente(lol) if lol and user32.IsWindow(lol) else None
        if not info:
            time.sleep(0.2)
            continue
        left, top, w, h = info
        bgr = _shot(left, top, w, h)
        if bgr.size >= 16 and float(bgr.mean()) >= 5:
            nome, conf = _perguntar(bgr)
            if fixo is None:
                fixo = (nome, conf)
            elif nome == fixo[0]:
                fixo = (nome, conf)
                votos = []
            elif conf >= fixo[1] + 0.15:
                votos.append(nome)
                if len(votos) >= 3 and votos[-3:].count(nome) == 3:
                    fixo = (nome, conf)
                    votos = []
            else:
                votos = []
            nx, ny, nw, nh = _onde(bgr)
            if caixa is None:
                caixa = (nx, ny, nw, nh)
            else:
                caixa = (
                    int(caixa[0] * 0.7 + nx * 0.3),
                    int(caixa[1] * 0.7 + ny * 0.3),
                    int(caixa[2] * 0.7 + nw * 0.3),
                    int(caixa[3] * 0.7 + nh * 0.3),
                )
        if not fixo or not caixa:
            time.sleep(0.25)
            continue
        texto = f"{fixo[0]} {fixo[1]:.0%}"
        _label[0] = texto
        bx, by, bw, bh = caixa
        key = (texto, left + bx, top + by, bw, bh)
        if shown != key:
            user32.ShowWindow(overlay, SW_SHOWNA)
            _blit(overlay, left + bx, top + by, bw, bh, texto)
            shown = key
            _log(f"{texto} box {bw}x{bh}")
            _push_state(fixo[0], fixo[1])
        time.sleep(0.25)
    return 0


_started = False


def _push_state(nome: str, conf: float) -> None:
    try:
        from app_state import STATE
        STATE.update(vision_enabled=True, vision_champion=nome, vision_confidence=conf)
    except Exception:
        pass


def start_tracker() -> None:
    """Sobe o rastreador numa thread. O coach chama isto no start()."""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=run, daemon=True, name="vision-tracker").start()


if __name__ == "__main__":
    sys.exit(run())
