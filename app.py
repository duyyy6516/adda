import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import sys
import os

# Tự động tìm kiếm module ở thư mục hiện tại
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import các module nội bộ với xử lý ngoại lệ
try:
    from calculations import calculate_vpd, get_weather_by_time
    from services import send_telegram_message, get_quick_solution
    from analytics import (
        analyze_day_by_blocks_rt, 
        predict_vpd_trend_v3, 
        calculate_plant_stress_hours
    )
    from charts import (
        draw_temperature_chart, 
        draw_humidity_chart, 
        draw_vpd_chart
    )
except ModuleNotFoundError as e:
    st.error(f"❌ Không tìm thấy module bổ trợ: {e.name}")
    st.stop()

# --- CẤU HÌNH BAN ĐẦU ---
st.set_page_config(page_title="VPD Farm Analytics", page_icon="🌿", layout="wide")

DANH_SACH_CAY = {
    "🍓 Dâu tây Đà Lạt (Hoa / Trái)": (0.6, 1.1),
    "🍓 Dâu tây Đà Lạt (Giai đoạn ngó/cây con)": (0.4, 0.8),
    "🌹 Hoa hồng nhà kính (Đà Lạt)": (0.8, 1.3),
    "🌼 Hoa cúc / Hoa đồng tiền": (0.7, 1.2),
    "🍅 Cà chua bi / 🫑 Ớt chuông Palermo": (0.8, 1.4),
    "🥦 Súp lơ xanh / Bắp cabbage baby": (0.5, 1.0),
    "🥬 Xà lách Thủy canh (Lô lô, Romaine)": (0.4, 0.9),
    "🌱 Cây giống trong vườn ươm": (0.3, 0.7),
    "🛠️ Tùy chỉnh thủ công ngưỡng riêng": (0.8, 1.2)
}
plant_list_keys = list(DANH_SACH_CAY.keys())

# Khởi tạo Session State vững chắc - Token & Chat ID được cố định tại đây
CHAU_HINH_MAC_DINH = {
    "temp": 0.0, "rh": 0.0, "countdown": 15,
    "is_running": False, "is_completed": False, "history": [],
    "stt_counter": 0, "plant_idx": 0, "vpd_range_val": (0.6, 1.1),
    "simulated_time": "2026-05-24 07:00:00", "file_plant_idx": 0,
    "file_vpd_range_val": (0.6, 1.1), 
    "tele_token_input": "8917951413:AAE6LKUEfYEYiQrFWGoKsQn0tumZc_XbcHg",
    "tele_chat_id_input": "7290661009"
}
for key, val in CHAU_HINH_MAC_DINH.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Nhúng CSS tối ưu giao diện gọn gàng
st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"] { overflow-y: auto !important; scroll-behavior: smooth; }
    .block-container { padding: 2rem 1.5rem 4rem 1.5rem; }
    .danger-box-red { padding: 12px; background-color: #FFEBEE; border-left: 6px solid #FF1744; color: #B71C1C; font-weight: bold; border-radius: 4px; margin-bottom: 8px; }
    .danger-box-blue { padding: 12px; background-color: #E3F2FD; border-left: 6px solid #2979FF; color: #0D47A1; font-weight: bold; border-radius: 4px; margin-bottom: 8px; }
    .upload-header { font-size: 16px; font-weight: bold; color: #1A5276; border-bottom: 2px solid #D4E6F1; padding-bottom: 5px; margin-bottom: 12px; }
    .metric-card-upload { background-color: #F4F6F7; border: 1px solid #E5E7E9; padding: 10px; border-radius: 6px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- HÀM BỔ TRỢ GIAO DIỆN ---
def style_status_rows(row):
    styles = [''] * len(row)
    idx = row.index.get_loc('Trạng thái')
    status = str(row['Trạng thái'])
    if "Lý tưởng" in status:
        styles[idx] = 'background-color: #E8F5E9; color: #1B5E20; font-weight: bold;'
    elif "Quá khô" in status:
        styles[idx] = 'background-color: #FFEBEE; color: #B71C1C; font-weight: bold;'
    elif "Quá ẩm" in status:
        styles[idx] = 'background-color: #E3F2FD; color: #0D47A1; font-weight: bold;'
    return styles

def setup_next_day():
    current_dt = datetime.strptime(st.session_state.simulated_time, "%Y-%m-%d %H:%M:%S")
    if current_dt.hour == 0 and current_dt.minute == 0:
        next_dt = current_dt + timedelta(hours=7)
    else:
        next_dt = current_dt + timedelta(days=1)
        next_dt = next_dt.replace(hour=7, minute=0, second=0)
    st.session_state.simulated_time = next_dt.strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.is_completed = False
    st.session_state.countdown = 15

def trigger_new_data(v_min, v_max):
    cur_sim = datetime.strptime(st.session_state.simulated_time, "%Y-%m-%d %H:%M:%S")
    day_str = cur_sim.strftime("Ngày %d/%m")
    
    st.session_state.temp, st.session_state.rh = get_weather_by_time(cur_sim)
    st.session_state.countdown = 15 
    st.session_state.stt_counter += 1
    
    t_val, h_val = st.session_state.temp, st.session_state.rh
    new_vpd = calculate_vpd(t_val, h_val)
    
    if new_vpd < v_min:
        status_text, tele_status = "⚠️ Quá ẩm", "🟦 QUÁ ẨM"
    elif new_vpd <= v_max:
        status_text, tele_status = "✅ Lý tưởng", "🟩 LÝ TƯỞNG"
    else:
        status_text, tele_status = "🚨 Quá khô", "🟥 QUÁ KHÔ"
    
    st.session_state.history.insert(0, {
        "STT": st.session_state.stt_counter, "Ngày": day_str,
        "Thời gian mô phỏng": cur_sim, "Hiển thị Giờ": cur_sim.strftime("%H:%M"),
        "datetime_internal": cur_sim, "Nhiệt độ (°C)": t_val, "Độ ẩm (%)": h_val,
        "VPD (kPa)": round(new_vpd, 2), "Trạng thái": status_text
    })
    
    t_token = st.session_state.tele_token_input
    t_chat_id = st.session_state.tele_chat_id_input
    if t_token and t_chat_id:
        sol = get_quick_solution(new_vpd, v_min, v_max, cur_sim.hour)
        u_days = sorted(list(set([r["Ngày"] for r in st.session_state.history])), reverse=True)
        lat_day = u_days[0] if u_days else day_str
        hist_lat = [r for r in st.session_state.history if r["Ngày"] == lat_day]
        trend, t_type = predict_vpd_trend_v3(hist_lat, cur_sim.hour, v_min, v_max)
        pfx = "🚨 [CẢNH BÁO SỚM] " if "CẢNH BÁO SỚM" in trend else ""
        
        msg = (
            f"🌿 **HỆ THỐNG VPD ĐÀ LẠT REALTIME**\n"
            f"⏰ {day_str} - {cur_sim.strftime('%H:%M')}\n"
            f"📊 Môi trường: {t_val}°C | {h_val}%\n\n"
            f"**1️⃣ Hiện trạng:** **{new_vpd:.2f} kPa** — {tele_status}\n"
            f"**2️⃣ Biện pháp:** *{sol}*\n"
            f"**3️⃣ Dự báo:** {pfx}*{trend}*"
        )
        send_telegram_message(t_token, t_chat_id, msg)
    
    nxt_sim = cur_sim + timedelta(minutes=10)
    if nxt_sim.hour == 0 and nxt_sim.minute == 0:
        st.session_state.is_running = False     
        st.session_state.is_completed = True   
    st.session_state.simulated_time = nxt_sim.strftime("%Y-%m-%d %H:%M:%S")

# --- PHÂN TÁCH CÁC THÀNH PHẦN GIAO DIỆN CHÍNH ---
def render_sidebar_controls():
    st.markdown("<h3 style='color:#2E7D32;font-size:18px;'>🤖 TRẠM ĐIỀU HÀNH</h3>", unsafe_allow_html=True)
    with st.container(border=True):
        cb1, cb2 = st.columns(2)
        with cb1:
            if st.button("▶️ Bắt đầu", type="primary", use_container_width=True, disabled=st.session_state.is_running):
                if st.session_state.is_completed: setup_next_day()
                st.session_state.is_running = True
                if st.session_state.stt_counter == 0: 
                    trigger_new_data(st.session_state.vpd_range_val[0], st.session_state.vpd_range_val[1])
                st.rerun()
        with cb2:
            if st.button("⏸️ Tạm dừng", type="secondary", use_container_width=True, disabled=not st.session_state.is_running):
                st.session_state.is_running = False
                st.rerun()
                
    with st.container(border=True):
        opt = st.selectbox("Cây trồng mô phỏng:", plant_list_keys, index=st.session_state.plant_idx, disabled=st.session_state.is_running)
        st.session_state.plant_idx = plant_list_keys.index(opt)
        v_range = DANH_SACH_CAY[opt] if opt != "🛠️ Tùy chỉnh thủ công ngưỡng riêng" else st.session_state.vpd_range_val
        vpd_sc = st.slider("Khoảng tối ưu (kPa):", 0.0, 3.0, v_range, 0.1, disabled=st.session_state.is_running or (opt != "🛠️ Tùy chỉnh thủ công ngưỡng riêng"))
        st.session_state.vpd_range_val = vpd_sc

    # Khung giám sát thời gian thực bên trái
    run_interval = 1 if st.session_state.is_running else 999999
    @st.fragment(run_every=run_interval)
    def live_monitor():
        v_min, v_max = st.session_state.vpd_range_val
        if st.session_state.is_running:
            st.session_state.countdown -= 1
            if st.session_state.countdown < 0: 
                trigger_new_data(v_min, v_max)
                st.rerun()
        if st.session_state.is_running: st.caption(f"⏳ Đổi số sau: **{st.session_state.countdown}s**")
        elif st.session_state.is_completed: st.success("🏁 Hoàn thành chu kỳ ngày!")

        c_sim = datetime.strptime(st.session_state.simulated_time, "%Y-%m-%d %H:%M:%S")
        with st.container(border=True):
            st.markdown(f"⏰ **{c_sim.strftime('Ngày %d/%m')} — {c_sim.strftime('%H:%M')}**")
            c1, c2 = st.columns(2)
            c1.metric("🌡️ Nhiệt độ", f"{st.session_state.temp}°C" if st.session_state.stt_counter > 0 else "--°C")
            c2.metric("💧 Độ ẩm", f"{st.session_state.rh}%" if st.session_state.stt_counter > 0 else "--%")

        v_res = calculate_vpd(st.session_state.temp, st.session_state.rh)
        with st.container(border=True):
            st.markdown("<p style='color:#2E7D32;font-weight:bold;margin-bottom:2px;'>🎯 LỆNH ĐIỀU HÀNH</p>", unsafe_allow_html=True)
            if st.session_state.stt_counter == 0:
                st.info("Đang chờ kích hoạt...")
            else:
                lbl, color = ("🟩 LÝ TƯỞNG", "#2E7D32") if v_min <= v_res <= v_max else (("🟦 QUÁ ẨM", "#0068C9") if v_res < v_min else ("🟥 QUÁ KHÔ", "#FF4B4B"))
                u_days = sorted(list(set([r["Ngày"] for r in st.session_state.history])), reverse=True)
                hist_lat = [r for r in st.session_state.history if r["Ngày"] == (u_days[0] if u_days else c_sim.strftime("Ngày %d/%m"))]
                trnd, t_tp = predict_vpd_trend_v3(hist_lat, c_sim.hour, v_min, v_max)
                
                if t_tp == "danger_red": st.markdown(f"<div class='danger-box-red'>🚨 {trnd}</div>", unsafe_allow_html=True)
                elif t_tp == "danger_blue": st.markdown(f"<div class='danger-box-blue'>🚨 {trnd}</div>", unsafe_allow_html=True)
                st.markdown(f"**VPD:** <span style='color:{color};font-weight:bold;font-size:16px;'>{v_res:.2f} kPa</span> ({lbl})", unsafe_allow_html=True)
                st.markdown(f"**Biện pháp:** _{get_quick_solution(v_res, v_min, v_max, c_sim.hour)}_")
                if t_tp not in ["danger_red", "danger_blue"]: st.markdown(f"**Dự báo:** {trnd}")
    live_monitor()

def render_realtime_analytics_panel():
    st.markdown("<h3 style='color:#2E7D32;font-size:18px;'>📊 TRUNG TÂM PHÂN TÍCH CHU KỲ REALTIME</h3>", unsafe_allow_html=True)
    if not st.session_state.history:
        st.info("Chưa có số liệu. Vui lòng nhấn nút Bắt đầu để tải.")
        return
        
    u_days = sorted(list(set([r["Ngày"] for r in st.session_state.history])), reverse=True)
    f1, f2 = st.columns([7, 3])
    sel_day = f1.selectbox("Lọc ngày:", u_days, label_visibility="collapsed")
    if f2.button("🗑️ Reset All", use_container_width=True):
        st.session_state.update({"stt_counter": 0, "history": [], "simulated_time": "2026-05-24 07:00:00", "is_completed": False, "is_running": False})
        st.rerun()

    df_all = pd.DataFrame(st.session_state.history)
    df_f = df_all[df_all["Ngày"] == sel_day].iloc[::-1].copy()
    v_min, v_max = st.session_state.vpd_range_val

    t1, t2, t3 = st.tabs(["📈 Biểu đồ", "📊 Thống kê buổi", "📋 Nhật ký số liệu"])
    with t1:
        st.markdown("##### 🎯 Chỉ số VPD (kPa)")
        st.altair_chart(draw_vpd_chart(df_f, v_min, v_max), use_container_width=True)
        sc1, sc2 = st.columns(2)
        sc1.markdown("##### 🌡️ Nhiệt độ (°C)")
        sc1.altair_chart(draw_temperature_chart(df_f), use_container_width=True)
        sc2.markdown("##### 💧 Độ ẩm (%)")
        sc2.altair_chart(draw_humidity_chart(df_f), use_container_width=True)
    with t2:
        st.dataframe(analyze_day_by_blocks_rt(st.session_state.history, v_min, v_max, sel_day), use_container_width=True, hide_index=True)
    with t3:
        df_f["Thời gian"] = df_f["Hiển thị Giờ"]
        st.dataframe(df_f[["STT", "Thời gian", "Nhiệt độ (°C)", "Độ ẩm (%)", "VPD (kPa)", "Trạng thái"]].style.apply(style_status_rows, axis=1), use_container_width=True, hide_index=True)

# --- KHỞI CHẠY KHÔNG GIAN GIAO DIỆN TABS CHÍNH ---
tab_future, tab_past = st.tabs(["🔮 XEM DỰ BÁO & THEO DÕI TƯƠNG LAI", "📁 TẢI FILE & PHÂN TÍCH LỊCH SỬ"])

with tab_future:
    l_col, r_col = st.columns([3.5, 6.5])
    with l_col: render_sidebar_controls()
    with r_col: render_realtime_analytics_panel()

with tab_past:
    st.markdown("<h3 style='color:#1A5276;font-size:19px;'>📁 PHÂN TÍCH FILE IOT NHÀ KÍNH</h3>", unsafe_allow_html=True)
    tl, tr = st.columns(2)
    with tl:
        with st.container(border=True):
            st.markdown("<div class='upload-header'>🌿 1. CẤU HÌNH LOẠI CÂY TRỒNG</div>", unsafe_allow_html=True)
            f_opt = st.selectbox("Chọn mô hình cây:", plant_list_keys, index=st.session_state.file_plant_idx)
            st.session_state.file_plant_idx = plant_list_keys.index(f_opt)
            f_rng = DANH_SACH_CAY[f_opt] if f_opt != "🛠️ Tùy chỉnh thủ công ngưỡng riêng" else st.session_state.file_vpd_range_val
            f_vpd_sc = st.slider("Ngưỡng tối ưu:", 0.0, 3.0, f_rng, 0.1, disabled=(f_opt != "🛠️ Tùy chỉnh thủ công ngưỡng riêng"))
            st.session_state.file_vpd_range_val = f_vpd_sc
            f_min, f_max = f_vpd_sc
    with tr:
        with st.container(border=True):
            st.markdown("<div class='upload-header'>📥 2. TẢI DỮ LIỆU ĐẦU VÀO</div>", unsafe_allow_html=True)
            u_file = st.file_uploader("Kéo thả file:", type=["json", "csv", "xlsx"], label_visibility="collapsed")
            t_filter = st.selectbox("📆 Chế độ lọc và gộp:", ["📊 Xem toàn bộ dữ liệu gốc", "📆 Tự chọn ngày cụ thể", "🗓️ Chọn 1 tháng (29 ngày)", "📅 Chọn 1 tuần (6 ngày)", "⏱️ 1 Ngày gần nhất (Gom 10p)", "📅 1 Tuần gần nhất (Gom ngày)", "🗓️ 1 Tháng gần nhất (Gom ngày)"])

    if u_file:
        try:
            if u_file.name.endswith('.json'):
                j_data = json.load(u_file)
                df_up = pd.DataFrame([j_data]) if isinstance(j_data, dict) and not isinstance(list(j_data.values())[0], (dict, list)) else pd.DataFrame(j_data)
            elif u_file.name.endswith('.csv'): df_up = pd.read_csv(u_file)
            else: df_up = pd.read_excel(u_file)
                
            c_t, c_h, c_time = None, None, None
            for c in df_up.columns:
                cl = str(c).lower().strip()
                if 'tempkk' in cl: c_t = c
                if 'humikk' in cl: c_h = c
                if any(k in cl for k in ['thời gian', 'time', 'gio', 'date', 'timestamp', 'created_at']): c_time = c

            if not c_t:
                for c in df_up.columns:
                    cl = str(c).lower().strip()
                    if any(k in cl for k in ['temp', 'nhiet', 't°', 'temperature']): c_t = c
            if not c_h:
                for c in df_up.columns:
                    cl = str(c).lower().strip()
                    if any(k in cl for k in ['rh', 'hum', 'do am', 'humidity']): c_h = c

            if not c_t and len(df_up.columns) > 0: c_t = df_up.columns[0]
            if not c_h and len(df_up.columns) > 1: c_h = df_up.columns[1]
            if not c_time and len(df_up.columns) > 2: c_time = df_up.columns[2]

            r_dts = []
            for val in df_up[c_time].astype(str):
                cv = val.strip()
                try:
                    if " " in cv and "-" in cv.split(" ")[1]:
                        dp, tp = cv.split(" ")
                        r_dts.append(datetime.strptime(f"{dp} {tp.replace('-', ':')}", "%Y-%m-%d %H:%M:%S"))
                    else: r_dts.append(pd.to_datetime(cv))
                except Exception: r_dts.append(datetime.now())

            df_rc = pd.DataFrame()
            df_rc["datetime_internal"] = r_dts
            df_rc["Nhiệt độ (°C)"] = pd.to_numeric(df_up[c_t], errors='coerce').apply(lambda x: x / 10.0 if pd.notna(x) and x >= 45.0 else x)
            df_rc["Độ ẩm (%)"] = pd.to_numeric(df_up[c_h], errors='coerce').apply(lambda x: x / 100.0 if pd.notna(x) and x > 100.0 else x)
            df_rc = df_rc[df_rc["Độ ẩm (%)"] > 1.0].dropna().sort_values("datetime_internal")

            if len(df_rc) > 0:
                df_rc["VPD_raw"] = df_rc.apply(lambda r: calculate_vpd(r["Nhiệt độ (°C)"], r["Độ ẩm (%)"]), axis=1)
                df_rc["only_date"] = df_rc["datetime_internal"].dt.date
                av_dates = sorted(df_rc["only_date"].unique())
                
                if "Tự chọn ngày cụ thể" in t_filter:
                    s_date = st.date_input("👇 Chọn ngày:", value=av_dates[-1] if av_dates else datetime.now().date())
                    df_rc = df_rc[df_rc["only_date"] == s_date]
                elif "29 ngày" in t_filter:
                    st_d = st.date_input("👇 Ngày bắt đầu:", value=av_dates[0] if av_dates else datetime.now().date())
                    df_rc = df_rc[(df_rc["only_date"] >= st_d) & (df_rc["only_date"] <= st_d + timedelta(days=29))]
                elif "6 ngày" in t_filter:
                    st_d = st.date_input("👇 Ngày bắt đầu:", value=av_dates[0] if av_dates else datetime.now().date())
                    df_rc = df_rc[(df_rc["only_date"] >= st_d) & (df_rc["only_date"] <= st_d + timedelta(days=6))]
                elif "Xem toàn bộ dữ liệu gốc" in t_filter: pass
                else:
                    m_time = df_rc["datetime_internal"].max()
                    if "1 Ngày gần nhất" in t_filter: df_rc = df_rc[df_rc["datetime_internal"] >= (m_time - timedelta(days=1))]
                    elif "1 Tuần gần nhất" in t_filter: df_rc = df_rc[df_rc["datetime_internal"] >= (m_time - timedelta(days=7))]
                    elif "1 Tháng gần nhất" in t_filter: df_rc = df_rc[df_rc["datetime_internal"] >= (m_time - timedelta(days=30))]

            df_f_blk = df_rc.copy()

            if len(df_rc) > 0:
                u_days_f = df_rc["only_date"].nunique()
                df_rs = df_rc[["datetime_internal", "Nhiệt độ (°C)", "Độ ẩm (%)", "VPD_raw"]].copy().set_index("datetime_internal")
                
                if any(k in t_filter for k in ["1 Tuần gần nhất", "1 Tháng gần nhất", "ngày"]):
                    df_rs = df_rs.resample("1D").mean().dropna()
                elif "Xem toàn bộ dữ liệu gốc" in t_filter:
                    df_rs = df_rs.resample("1h" if u_days_f > 2 else "10min").mean().dropna()
                elif "1 Ngày gần nhất" in t_filter:
                    df_rs = df_rs.resample("10min").mean().dropna()
                
                df_rs["datetime_internal"] = df_rs.index
                fmt = "%d/%m %H:%M" if (any(k in t_filter for k in ["1 Tuần gần nhất", "1 Tháng gần nhất", "ngày"]) or ("Xem toàn bộ dữ liệu gốc" in t_filter and u_days_f > 2)) else "%H:%M"
                df_rs["Hiển thị Giờ"] = df_rs["datetime_internal"].dt.strftime(fmt)
                df_rs.reset_index(drop=True, inplace=True)
            else:
                u_days_f = 0
                df_rs = pd.DataFrame(columns=["datetime_internal", "Nhiệt độ (°C)", "Độ ẩm (%)", "VPD_raw", "Hiển thị Giờ"])

            df_p = pd.DataFrame()
            df_p["datetime_internal"] = df_rs["datetime_internal"]
            df_p["Nhiệt độ (°C)"] = df_rs["Nhiệt độ (°C)"].round(2)
            df_p["Độ ẩm (%)"] = df_rs["Độ ẩm (%)"].round(2)
            df_p["Hiển thị Giờ"] = df_rs["Hiển thị Giờ"]
            df_p["VPD (kPa)"] = df_rs["VPD_raw"].round(2) if u_days_f > 2 else df_p.apply(lambda r: round(calculate_vpd(r["Nhiệt độ (°C)"], r["Độ ẩm (%)"]), 2), axis=1)
            df_p["Ngày"] = "Dữ liệu File"
            df_p["Trạng thái"] = df_p["VPD (kPa)"].apply(lambda x: "⚠️ Quá ẩm" if x < f_min else ("✅ Lý tưởng" if x <= f_max else "🚨 Quá khô"))
            
            # --- KHỐI THỐNG KÊ (KPIs) ---
            st.markdown("<div style='margin-top:15px;margin-bottom:5px;font-weight:bold;color:#1A5276;'>📊 TỔNG QUAN CHU KỲ GỘP</div>", unsafe_allow_html=True)
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.markdown(f"<div class='metric-card-upload'><span>📈 VPD TB CHU KỲ</span><br><b style='font-size:18px;color:#2E7D32;'>{df_p['VPD (kPa)'].mean():.2f} kPa</b></div>", unsafe_allow_html=True)
            mc2.markdown(f"<div class='metric-card-upload'><span>🌡️ NHIỆT ĐỘ TB</span><br><b style='font-size:18px;color:#FF4B4B;'>{df_p['Nhiệt độ (°C)'].mean():.1f} °C</b></div>", unsafe_allow_html=True)
            mc3.markdown(f"<div class='metric-card-upload'><span>💧 ĐỘ ẨM TB</span><br><b style='font-size:18px;color:#0068C9;'>{df_p['Độ ẩm (%)'].mean():.1f} %</b></div>", unsafe_allow_html=True)
            mc4.markdown(f"<div class='metric-card-upload'><span>📋 SỐ ĐIỂM DỮ LIỆU</span><br><b style='font-size:18px;color:#5D6D7E;'>{len(df_p)} điểm</b></div>", unsafe_allow_html=True)

            # --- ĐÁNH GIÁ STRESS ---
            str_res = calculate_plant_stress_hours(df_p, f_min, f_max, t_filter)
            st.markdown("<div style='margin-top:10px;font-weight:bold;color:#B71C1C;'>⚠️ ĐÁNH GIÁ CHUYÊN SÂU ÁP LỰC CÂY TRỒNG</div>", unsafe_allow_html=True)
            sc_l, sc_r = st.columns(2)
            if str_res["dry_hours"] > 2.0: sc_l.error(f"🚨 **Stress Khô Nóng:** Bị đóng khí khổng suốt **{str_res['dry_hours']} giờ**.")
            else: sc_l.success(f"✅ **Áp lực khô:** An toàn ({str_res['dry_hours']} giờ).")
            if str_res["wet_hours"] > 4.0: sc_r.warning(f"🟦 **Stress Ẩm:** Tích tụ ẩm cao liên tục **{str_res['wet_hours']} giờ**.")
            else: sc_r.success(f"✅ **Áp lực ẩm:** An toàn ({str_res['wet_hours']} giờ).")

            # --- VẼ ĐỒ THỊ FILE VÀ BẢNG SỐ LIỆU ---
            rl, rr = st.columns([6.2, 3.8])
            with rl:
                st.markdown("#### 📊 BIỂU ĐỒ CHU KỲ PHÂN TẦNG")
                st.markdown("##### 🎯 Chỉ số VPD (kPa)")
                st.altair_chart(draw_vpd_chart(df_p, f_min, f_max), use_container_width=True)
                sfc1, sfc2 = st.columns(2)
                sfc1.markdown("##### 🌡️ Nhiệt độ (°C)")
                sfc1.altair_chart(draw_temperature_chart(df_p), use_container_width=True)
                sfc2.markdown("##### 💧 Độ ẩm (%)")
                sfc2.altair_chart(draw_humidity_chart(df_p), use_container_width=True)
            with rr:
                st.markdown("##### 📋 NHẬT KÝ THEO DÕI ĐIỂM GỘP CHU KỲ")
                df_tc = df_p[["Hiển thị Giờ", "Nhiệt độ (°C)", "Độ ẩm (%)", "VPD (kPa)", "Trạng thái"]].copy()
                for c in ["Nhiệt độ (°C)", "Độ ẩm (%)", "VPD (kPa)"]: df_tc[c] = df_tc[c].apply(lambda x: f"{float(x):.2f}")
                st.dataframe(df_tc.style.apply(style_status_rows, axis=1), use_container_width=True, hide_index=True, height=290)
                st.download_button("📥 Xuất báo cáo chu kỳ (.csv)", data=df_p.to_csv(index=False).encode('utf-8'), file_name="vpd_report.csv", mime="text/csv", use_container_width=True)

            # --- BÁO CÁO THEO BUỔI ---
            st.markdown("---")
            st.markdown("##### 📊 BÁO CÁO PHÂN TÍCH TỔNG HỢP THEO BUỔI CHU KỲ (Dữ liệu gốc)")
            if len(df_f_blk) > 0:
                df_f_blk["Hour"] = df_f_blk["datetime_internal"].dt.hour
                def b_assign(h):
                    if 5 <= h < 10: retuimport streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import sys
import os

# Tự động tìm kiếm module ở thư mục hiện tại
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import các module nội bộ với xử lý ngoại lệ
try:
    from calculations import calculate_vpd, get_weather_by_time
    from services import send_telegram_message, get_quick_solution
    from analytics import (
        analyze_day_by_blocks_rt, 
        predict_vpd_trend_v3, 
        calculate_plant_stress_hours
    )
    from charts import (
        draw_temperature_chart, 
        draw_humidity_chart, 
        draw_vpd_chart
    )
except ModuleNotFoundError as e:
    st.error(f"❌ Không tìm thấy module bổ trợ: {e.name}")
    st.stop()

# --- CẤU HÌNH BAN ĐẦU ---
st.set_page_config(page_title="VPD Farm Analytics", page_icon="🌿", layout="wide")

DANH_SACH_CAY = {
    "🍓 Dâu tây Đà Lạt (Hoa / Trái)": (0.6, 1.1),
    "🍓 Dâu tây Đà Lạt (Giai đoạn ngó/cây con)": (0.4, 0.8),
    "🌹 Hoa hồng nhà kính (Đà Lạt)": (0.8, 1.3),
    "🌼 Hoa cúc / Hoa đồng tiền": (0.7, 1.2),
    "🍅 Cà chua bi / Ớt chuông Sweet Palerma": (0.8, 1.4),
    "🥬 Xà lách thủy canh / Rau ăn lá": (0.4, 0.95),
    "Custom (Tự nhập dải biên mục tiêu)": (0.0, 0.0)
}

# Khởi tạo trạng thái phiên làm việc (Session State)
if "history" not in st.session_state:
    st.session_state.history = []
if "sim_time" not in st.session_state:
    st.session_state.sim_time = datetime.now()
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# Giao diện Sidebar điều khiển và cấu hình
st.sidebar.markdown("### ⚙️ Cấu hình Hệ thống & Cây trồng")
loai_cay = st.sidebar.selectbox("Chọn loại cây trồng mục tiêu:", list(DANH_SACH_CAY.keys()))

if loai_cay == "Custom (Tự nhập dải biên mục tiêu)":
    vpd_min = st.sidebar.number_input("Biên VPD Dưới (kPa):", min_value=0.0, max_value=3.0, value=0.5, step=0.1)
    vpd_max = st.sidebar.number_input("Biên VPD Trên (kPa):", min_value=0.0, max_value=3.0, value=1.2, step=0.1)
else:
    vpd_min, vpd_max = DANH_SACH_CAY[loai_cay]
    st.sidebar.info(f"📍 Dải biên VPD khuyến nghị: **{vpd_min} - {vpd_max} kPa**")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔔 Tích hợp Cảnh báo Telegram")
bot_token = st.sidebar.text_input("Telegram Bot Token:", type="password", help="Nhập token nhận từ BotFather")
chat_id = st.sidebar.text_input("Telegram Chat ID:", help="ID nhóm hoặc ID cá nhân nhận tin nhắn")

# Tiêu đề giao diện chính
st.markdown("<h2 style='text-align: center; color: #2E7D32;'>🌿 Hệ Thống Phân Tích & Giám Sát Chỉ Số VPD Farm</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555;'>Mô phỏng thời gian thực nâng cao theo chu kỳ khí hậu Đà Lạt - Quét lỗi treo cảm biến & Báo cáo tổng hợp</p>", unsafe_allow_html=True)

# Khối điều khiển dòng thời gian mô phỏng
st.markdown("---")
col_ctrl1, col_ctrl2, col_ctrl3, col_ctrl4 = st.columns([2, 2, 2, 3])

with col_ctrl1:
    if st.button("🔄 Chạy / Cập nhật mốc tiếp theo", use_container_width=True):
        st.session_state.sim_time += timedelta(hours=1)
        st.session_state.is_running = True
        
        # Lấy thời tiết mô phỏng và tính VPD
        t_sim, h_sim = get_weather_by_time(st.session_state.sim_time)
        v_sim = round(calculate_vpd(t_sim, h_sim), 2)
        
        # Xác định trạng thái
        if v_sim < vpd_min:
            stat_sim = "⚠️ Quá ẩm"
        elif v_sim > vpd_max:
            stat_sim = "⚠️ Quá khô"
        else:
            stat_sim = "✅ An toàn"
            
        new_entry = {
            "Thời điểm (Mô phỏng)": st.session_state.sim_time.strftime("%d/%m/%Y %H:%M"),
            "datetime_internal": st.session_state.sim_time,
            "Nhiệt độ (°C)": t_sim,
            "Độ ẩm (%)": h_sim,
            "VPD (kPa)": v_sim,
            "VPD_raw": v_sim,
            "Trạng thái": stat_sim,
            "Hiển thị Giờ": st.session_state.sim_time.strftime("%H:%M")
        }
        
        # Thêm vào đầu danh sách lịch sử để phục vụ phân tích độ dốc của v3
        st.session_state.history.insert(0, new_entry)

with col_ctrl2:
    if st.button("🧹 Xóa sạch bộ nhớ lịch sử", use_container_width=True):
        st.session_state.history = []
        st.session_state.sim_time = datetime.now()
        st.session_state.is_running = False
        st.rerun()

with col_ctrl3:
    # Nút bấm tính năng mở rộng: Mô phỏng kẹt lỗi đứng im dữ liệu để test thuật toán v3
    if st.button("🚨 Giả lập lỗi kẹt cảm biến", use_container_width=True):
        if len(st.session_state.history) > 0:
            st.session_state.sim_time += timedelta(hours=1)
            last_item = st.session_state.history[0]
            stuck_entry = {
                "Thời điểm (Mô phỏng)": st.session_state.sim_time.strftime("%d/%m/%Y %H:%M"),
                "datetime_internal": st.session_state.sim_time,
                "Nhiệt độ (°C)": last_item["Nhiệt độ (°C)"],
                "Độ ẩm (%)": last_item["Độ ẩm (%)"],
                "VPD (kPa)": last_item["VPD (kPa)"],
                "VPD_raw": last_item["VPD_raw"],
                "Trạng thái": last_item["Trạng thái"],
                "Hiển thị Giờ": st.session_state.sim_time.strftime("%H:%M")
            }
            st.session_state.history.insert(0, stuck_entry)
        else:
            st.warning("Hãy bấm cập nhật một vài mốc thời gian trước khi thử nghiệm giả lập kẹt dữ liệu!")

with col_ctrl4:
    st.markdown(f"**⏰ Thời gian hệ thống hiện tại:** `{st.session_state.sim_time.strftime('%d/%m/%Y %H:%M')}`")

# Hiển thị dữ liệu tức thời nếu có dữ liệu
if st.session_state.history:
    cur_data = st.session_state.history[0]
    
    # 1. KHỐI THÔNG SỐ REALTIME CƠ BẢN
    st.markdown("### 📊 Thông số giám sát tức thời")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("🌡️ Nhiệt độ không khí", f"{cur_data['Nhiệt độ (°C)']} °C")
    with col_m2:
        st.metric("💧 Độ ẩm tương đối (RH)", f"{cur_data['Độ ẩm (%)']} %")
    with col_m3:
        st.metric("💨 Chỉ số thâm hụt áp suất (VPD)", f"{cur_data['VPD (kPa)']} kPa")
    with col_m4:
        color_map = {"✅ An toàn": "green", "⚠️ Quá ẩm": "blue", "⚠️ Quá khô": "orange"}
        lbl_status = cur_data['Trạng thái']
        st.markdown(f"<div style='background-color:#f9f9f9; padding: 10px; border-radius: 5px; text-align: center; border-left: 5px solid {color_map.get(lbl_status, 'gray')};'><b>Trạng thái Vi khí hậu:</b><br><span style='font-size: 18px; color:{color_map.get(lbl_status, 'black')};'>{lbl_status}</span></div>", unsafe_allow_html=True)

    # 2. KHỐI PHÂN TÍCH THUẬT TOÁN ALGORITHMS (Xu hướng v3 & Giờ căng thẳng)
    st.markdown("---")
    st.markdown("### 🧠 Phân tích Xu hướng & Ổn định Sinh học (Thuật toán v3)")
    col_an1, col_an2 = st.columns(2)
    
    with col_an1:
        st.markdown("##### 📈 Dự báo Xu hướng & Quét lỗi cảm biến")
        trend_msg, trend_code = predict_vpd_trend_v3(st.session_state.history, cur_data["datetime_internal"].hour, vpd_min, vpd_max)
        if trend_code == "danger_stuck":
            st.error(trend_msg)
        elif trend_code == "danger_high" or trend_code == "danger_low":
            st.warning(trend_msg)
        elif trend_code == "normal_up" or trend_code == "normal_down":
            st.info(trend_msg)
        else:
            st.success(trend_msg)
            
        # Tự động gửi cảnh báo nếu phát hiện nguy cơ bất thường và có cài đặt cấu hình Bot Telegram
        if trend_code in ["danger_stuck", "danger_high", "danger_low"] and bot_token and chat_id:
            alert_text = f"🚨 **CẢNH BÁO VPD CÂY TRỒNG ({loai_cay})**\n⏰ Thời gian: {cur_data['Thời điểm (Mô phỏng)']}\n📈 VPD Hiện tại: {cur_data['VPD (kPa)']} kPa\n🔍 Phân tích hệ thống: {trend_msg}"
            success = send_telegram_message(bot_token, chat_id, alert_text)
            if success:
                st.toast("📲 Đã gửi cảnh báo khẩn cấp đến Telegram của chủ vườn!", icon="🚀")

    with col_an2:
        st.markdown("##### 🕒 Quản lý Số giờ tích lũy Căng thẳng của Cây (Stress Hours)")
        df_for_stress = pd.DataFrame(st.session_state.history)
        # Ép kiểu dữ liệu an toàn
        df_for_stress["VPD (kPa)"] = df_for_stress["VPD (kPa)"].astype(float)
        stress_h = calculate_plant_stress_hours(df_for_stress, vpd_min, vpd_max)
        
        if stress_h > 4:
            st.markdown(f"<div style='color: #D32F2F; font-size: 16px; font-weight: bold;'>⚠️ Cây trồng đã chịu áp lực stress liên tục {stress_h} giờ qua. Năng suất sinh học đang bị sụt giảm nặng!</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='color: #388E3C; font-size: 16px; font-weight: bold;'>✅ Tổng số giờ áp lực stress trong chu kỳ: {stress_h} giờ. Cây đang nằm trong ngưỡng chịu đựng tốt.</div>", unsafe_allow_html=True)
            
        # Đưa ra giải pháp nhanh xử lý vi khí hậu thời gian thực
        quick_sol = get_quick_solution(cur_data['VPD (kPa)'], vpd_min, vpd_max, cur_data['datetime_internal'].hour)
        st.markdown(f"💡 **Khuyến nghị vận hành:** {quick_sol}")

    # 3. ĐỒ THỊ TRỰC QUAN HÓA (Xếp dạng hàng ngang)
    st.markdown("---")
    st.markdown("### 📉 Đồ thị theo dõi Biến động Dữ liệu Lịch sử")
    
    # Chuẩn bị dữ liệu vẽ đồ thị (đảo ngược lại để hiển thị mốc thời gian xuôi dòng từ trái qua phải)
    df_chart_source = pd.DataFrame(st.session_state.history).iloc[::-1].reset_index(drop=True)
    
    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        st.markdown("<p style='text-align: center; font-weight: bold; color: #FF4B4B;'>Biểu đồ Nhiệt độ không khí</p>", unsafe_allow_html=True)
        st.altair_chart(draw_temperature_chart(df_chart_source), use_container_width=True)
    with col_g2:
        st.markdown("<p style='text-align: center; font-weight: bold; color: #0068C9;'>Biểu đồ Độ ẩm (RH)</p>", unsafe_allow_html=True)
        st.altair_chart(draw_humidity_chart(df_chart_source), use_container_width=True)
    with col_g3:
        st.markdown("<p style='text-align: center; font-weight: bold; color: #2E7D32;'>Biểu đồ Dải An Toàn VPD Mục Tiêu</p>", unsafe_allow_html=True)
        st.altair_chart(draw_vpd_chart(df_chart_source, vpd_min, vpd_max), use_container_width=True)

    # 4. KHỐI HIỂN THỊ TUẦN TỰ (Đã bỏ st.tabs để gộp hiển thị thẳng xuống dưới đồ thị)
    df_f_blk = pd.DataFrame(st.session_state.history)

    # --- BÁO CÁO THEO BUỔI ---
    st.markdown("---")
    st.markdown("##### 📊 BÁO CÁO PHÂN TÍCH TỔNG HỢP THEO BUỔI CHU KỲ (Dữ liệu gốc)")
    if len(df_f_blk) > 0:
        df_f_blk["Hour"] = df_f_blk["datetime_internal"].dt.hour
        def b_assign(h):
            if 5 <= h < 10: return "🌅 Sáng (05h - 10h)"
            if 10 <= h < 15: return "☀️ Trưa (10h - 15h)"
            if 15 <= h < 19: return "🌇 Chiều (15h - 19h)"
            if 19 <= h < 23: return "🌌 Tối (19h - 23h)"
            return "🌙 Khuya (23h - 05h)"
        df_f_blk["Buổi"] = df_f_blk["Hour"].apply(b_assign)
        b_sum = df_f_blk.groupby("Buổi").agg({"Nhiệt độ (°C)": "mean", "Độ ẩm (%)": "mean", "VPD_raw": "mean"}).reindex(["🌅 Sáng (05h - 10h)", "☀️ Trưa (10h - 15h)", "🌇 Chiều (15h - 19h)", "🌌 Tối (19h - 23h)", "🌙 Khuya (23h - 05h)"]).dropna()
        
        blk_report = []
        for b_name, b_row in b_sum.iterrows():
            av_t = round(b_row["Nhiệt độ (°C)"], 1)
            av_h = round(b_row["Độ ẩm (%)"], 1)
            av_v = round(b_row["VPD_raw"], 2)
            if av_v < vpd_min:
                stt = "⚠️ Quá ẩm"
            elif av_v > vpd_max:
                stt = "⚠️ Quá khô"
            else:
                stt = "✅ Lý tưởng"
            blk_report.append({"Buổi": b_name, "Nhiệt độ TB (°C)": av_t, "Độ ẩm TB (%)": av_h, "VPD Trung bình (kPa)": av_v, "Đánh giá trạng thái": stt})
        
        if blk_report:
            st.dataframe(pd.DataFrame(blk_report), use_container_width=True, hide_index=True)
        else:
            st.info("Chưa đủ dữ liệu phân đoạn để lập báo cáo chu kỳ.")
    else:
        st.info("Chưa có dữ liệu để tổng hợp.")

    # --- NHẬT KÝ SỐ LIỆU LỊCH SỬ ---
    st.markdown("---")
    st.markdown("##### 📝 NHẬT KÝ SỐ LIỆU LỊCH SỬ CHI TIẾT (Bảng dữ liệu thô)")
    df_display = pd.DataFrame(st.session_state.history)
    if not df_display.empty:
        df_display_clean = df_display[["Thời điểm (Mô phỏng)", "Nhiệt độ (°C)", "Độ ẩm (%)", "VPD (kPa)", "Trạng thái"]]
        st.dataframe(df_display_clean, use_container_width=True, hide_index=True)
    else:
        st.info("Nhật ký trống. Vui lòng bấm cập nhật dữ liệu mô phỏng.")

else:
    st.info("👋 Chào mừng bạn đến với hệ thống quản lý VPD. Hãy bấm nút **'Chạy / Cập nhật mốc tiếp theo'** ở phía trên để bắt đầu mô phỏng và phân tích dữ liệu!")rn "🌅 Sáng (05h - 10h)"
                    if 10 <= h < 15: return "☀️ Trưa (10h - 15h)"
                    if 15 <= h < 19: return "🌇 Chiều (15h - 19h)"
                    if 19 <= h < 23: return "🌌 Tối (19h - 23h)"
                    return "🌙 Khuya (23h - 05h)"
                df_f_blk["Buổi"] = df_f_blk["Hour"].apply(b_assign)
                b_sum = df_f_blk.groupby("Buổi").agg({"Nhiệt độ (°C)": "mean", "Độ ẩm (%)": "mean", "VPD_raw": "mean"}).reindex(["🌅 Sáng (05h - 10h)", "☀️ Trưa (10h - 15h)", "🌇 Chiều (15h - 19h)", "🌌 Tối (19h - 23h)", "🌙 Khuya (23h - 05h)"]).dropna(how="all").reset_index()
                b_sum.columns = ["Khoảng thời gian", "Nhiệt độ TB (°C)", "Độ ẩm TB (%)", "VPD TB (kPa)"]
                for c in ["Nhiệt độ TB (°C)", "Độ ẩm TB (%)", "VPD TB (kPa)"]: b_sum[c] = b_sum[c].round(2)
                b_sum["Đánh giá"] = b_sum["VPD TB (kPa)"].apply(lambda x: "🟦 Quá ẩm" if x < f_min else ("🟩 Lý tưởng" if x <= f_max else "🟥 Quá khô"))
                st.dataframe(b_sum, use_container_width=True, hide_index=True)
        except Exception as file_err:
            st.error(f"❌ Lỗi xử lý file: {str(file_err)}")
