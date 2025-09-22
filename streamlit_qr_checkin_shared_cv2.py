
# 🎟️ QR Check-in (Shared Excel) — OpenCV-only (no ZBar)
# Semua klien sinkron pakai data/shared.xlsx. Webcam decode menggunakan cv2.QRCodeDetector().
import io, os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from filelock import FileLock
except Exception:
    FileLock = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# OpenCV for webcam + QR
try:
    import cv2
    import numpy as np
    _cv2_ok = True
except Exception:
    _cv2_ok = False

try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
    _webrtc_ok = True
except Exception:
    _webrtc_ok = False

st.set_page_config(page_title="QR Check-in (Shared, CV2-only)", page_icon="🎟️", layout="wide")
TZ = ZoneInfo("Asia/Jakarta")
TS_FMT = "%Y-%m-%d %H:%M:%S"

DATA_DIR = "data"
DATA_PATH = os.path.join(DATA_DIR, "shared.xlsx")
LOCK_PATH = DATA_PATH + ".lock"
os.makedirs(DATA_DIR, exist_ok=True)

BEEP_SRC = "data:audio/wav;base64,UklGRjQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQwAAAAAAP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wA="
def _beep():
    components.html(f"<audio autoplay src='{BEEP_SRC}'></audio>", height=0)

def _ensure_cols(df):
    df.columns = [str(c) for c in df.columns]
    if "ticket_id" not in df.columns:
        raise ValueError("Kolom 'ticket_id' wajib ada.")
    if "scanned_at" not in df.columns:
        df["scanned_at"] = pd.NaT
    if "scanned_by" not in df.columns:
        df["scanned_by"] = pd.NA
    return df

def load_shared_df():
    if not os.path.exists(DATA_PATH):
        return None
    if FileLock:
        with FileLock(LOCK_PATH):
            df = pd.read_excel(DATA_PATH)
    else:
        df = pd.read_excel(DATA_PATH)
    return _ensure_cols(df)

def save_shared_df(df):
    if FileLock:
        with FileLock(LOCK_PATH):
            df.to_excel(DATA_PATH, index=False)
    else:
        df.to_excel(DATA_PATH, index=False)

def _now_str():
    return datetime.now(TZ).strftime(TS_FMT)

def mark_scanned(ticket_value, who="Gate 1"):
    t = str(ticket_value or "").strip()
    if not t:
        return ("warn", "Ticket ID kosong.")
    cur = load_shared_df()
    if cur is None:
        return ("error", "Belum ada data/shared.xlsx")

    matches = cur["ticket_id"].astype(str).str.strip() == t
    if matches.sum() == 0:
        return ("error", f"Tiket {t} tidak ditemukan.")

    idxs = cur[matches].index.tolist()
    updated, already, infos = 0, 0, []
    for i in idxs:
        if pd.notna(cur.loc[i, "scanned_at"]):
            already += 1
            infos.append(str(cur.loc[i, "scanned_at"]))
        else:
            cur.loc[i, "scanned_at"] = _now_str()
            cur.loc[i, "scanned_by"] = who
            updated += 1
    save_shared_df(cur)

    if updated > 0 and already == 0:
        return ("ok", f"Tiket {t} ✅ ({updated} updated)")
    elif updated > 0:
        return ("warn", f"Tiket {t} sebagian sudah discan ({already}), {updated} baru.")
    else:
        return ("error", f"Tiket {t} SUDAH discan pada {', '.join(infos)}")

st.title("🎟️ QR Check-in (Shared Excel, CV2-only)")
st.caption("Tanpa ZBar/pyzbar. Webcam decode pakai OpenCV QRCodeDetector.")

with st.sidebar:
    st.header("Admin Upload")
    upl = st.file_uploader("Upload Excel", type=["xlsx"])
    if upl and st.button("Seed/Replace shared.xlsx"):
        try:
            df_up = pd.read_excel(upl)
            df_up = _ensure_cols(df_up)
            save_shared_df(df_up)
            st.success(f"File tersimpan ({len(df_up)} rows)")
        except Exception as e:
            st.error(f"Gagal: {e}")

    if st.button("Reset scanned_at/by"):
        cur = load_shared_df()
        if cur is not None:
            cur["scanned_at"] = pd.NaT
            cur["scanned_by"] = pd.NA
            save_shared_df(cur)
            st.success("Status scan direset")

    st.divider()
    st.caption("🔄 Auto-refresh UI (opsional)")
    if st_autorefresh:
        st_autorefresh(interval=3000, key="refresh")

df = load_shared_df()
if df is None:
    st.warning("Belum ada shared.xlsx, upload dulu di sidebar.")
    st.stop()

total = len(df)
scanned = df["scanned_at"].notna().sum()
c1, c2, c3 = st.columns(3)
c1.metric("Total", total)
c2.metric("Scanned", scanned)
c3.metric("Not Yet", total - scanned)

st.subheader("Scan / Input Ticket ID (Keyboard/Scanner)")
with st.form("scan_form", clear_on_submit=True):
    t_id = st.text_input("Ticket ID")
    who = st.text_input("Scanned by", value="Gate 1")
    sub = st.form_submit_button("Scan")
if sub:
    s, m = mark_scanned(t_id, who)
    _beep()
    getattr(st, "success" if s == "ok" else "warning" if s == "warn" else "error")(m)

st.divider()
st.subheader("📷 Mode Kamera (Webcam, OpenCV-only)")
if not _webrtc_ok:
    st.info("streamlit-webrtc belum terpasang. Install di server untuk webcam mode.")
if not _cv2_ok:
    st.info("OpenCV belum terpasang. Jalankan: pip install opencv-python-headless")

cam_enable = st.toggle("Aktifkan kamera", value=False, disabled=not (_webrtc_ok and _cv2_ok))
if cam_enable and _webrtc_ok and _cv2_ok:
    rtc_config = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
    last_ticket_placeholder = st.empty()
    if "last_camera_decode" not in st.session_state:
        st.session_state["last_camera_decode"] = None

    detector = cv2.QRCodeDetector()

    def on_frame(frame):
        img = frame.to_ndarray(format="bgr24")
        data, points, _ = detector.detectAndDecode(img)
        if data:
            tid = data.strip()
            if st.session_state["last_camera_decode"] != tid:
                st.session_state["last_camera_decode"] = tid
                s, m = mark_scanned(tid, who="Webcam")
                _beep()
                if s == "ok":
                    last_ticket_placeholder.success(f"[Webcam] {m}")
                elif s == "warn":
                    last_ticket_placeholder.warning(f"[Webcam] {m}")
                else:
                    last_ticket_placeholder.error(f"[Webcam] {m}")
        return frame

    webrtc_streamer(
        key="qr-webcam-shared-cv2",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=rtc_config,
        media_stream_constraints={"video": True, "audio": False},
        video_frame_callback=on_frame,
    )

st.subheader("Preview Data (Shared)")
st.dataframe(load_shared_df(), use_container_width=True)

st.subheader("Download Hasil (Shared)")
buf = io.BytesIO()
load_shared_df().to_excel(buf, index=False)
st.download_button("⬇️ Download", data=buf.getvalue(), file_name="AttendanceReport_SHARED.xlsx")
