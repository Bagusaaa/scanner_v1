import io, os, time
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

def mark_scanned(ticket_value, who=""):
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

st.title("🎟️ QR Check-in (Alur Production Indonesia)")

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

# === Form Scan ===
st.subheader("Scan / Input Ticket ID (Keyboard/Scanner)")
with st.form("scan_form", clear_on_submit=True):
    t_id = st.text_input("Ticket ID")
    who = st.text_input("Scanned by", value="Gate 1")
    sub = st.form_submit_button("Scan")

# --- Hasil Scan ---
if sub:
    s, m = mark_scanned(t_id, who)
    _beep()
    st.session_state["scan_result"] = (s, m)
    st.rerun()   # <- ganti ini, dan hanya di sini kita rerun

# --- Popup Notifikasi ---
if "scan_result" in st.session_state:
    s, m = st.session_state["scan_result"]
    color = "#64F43C" if s == "ok" else "#FFD146" if s == "warn" else "#FE1C0B"

    st.markdown(
        f"""
        <div style="
            position: fixed;
            top: 64px;
            left: 50%;
            transform: translate(-50%, 0%);
            background-color: {color};
            color: white;
            padding: 40px 60px;
            border-radius: 20px;
            font-size: 2rem;
            font-weight: bold;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            z-index: 9999;">
            {m}
        </div>
        """,
        unsafe_allow_html=True
    )

    import time
    time.sleep(2)
    st.session_state.pop("scan_result", None)
    # (tidak ada rerun di sini)

# === Preview & Download ===
st.subheader("Preview Data")

with st.expander("🔎 Search / Filter", expanded=True):
    q = st.text_input("Cari cepat (semua kolom)", placeholder="ketik mis. 292135 / 'Gate 1' / email / nama")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    f_ticket = c1.text_input("Ticket ID")
    f_user   = c2.text_input("Username")
    f_email  = c3.text_input("Email")
    f_phone  = c4.text_input("Phone")
    f_seat   = c5.text_input("Seat")
    f_status = c6.selectbox("Status", ["(any)", "Scanned", "Not Yet"], index=0)

# --- apply filters ---
view = df.copy()

# quick search (semua kolom)
if q:
    mask = False
    for col in view.columns:
        mask = mask | view[col].astype(str).str.contains(q, case=False, na=False)
    view = view[mask]

# column filters (opsional)
if f_ticket:
    view = view[view["ticket_id"].astype(str).str.contains(f_ticket, case=False, na=False)]
if f_user and "username" in view.columns:
    view = view[view["username"].astype(str).str.contains(f_user, case=False, na=False)]
if f_email and "email" in view.columns:
    view = view[view["email"].astype(str).str.contains(f_email, case=False, na=False)]
if f_phone and "phone" in view.columns:
    view = view[view["phone"].astype(str).str.contains(f_phone, case=False, na=False)]
if f_seat and "seat" in view.columns:
    view = view[view["seat"].astype(str).str.contains(f_seat, case=False, na=False)]

if f_status == "Scanned":
    view = view[view["scanned_at"].notna()]
elif f_status == "Not Yet":
    view = view[view["scanned_at"].isna()]

st.dataframe(view, use_container_width=True)

# Optional: download yang sudah terfilter
st.subheader("Download Hasil")
buf = io.BytesIO()
df.to_excel(buf, index=False)
st.download_button("⬇️ Download", data=buf.getvalue(), file_name="AttendanceReport_SHARED.xlsx")