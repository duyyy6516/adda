import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Import các hàm từ các file bạn đã cung cấp
from calculations import calculate_vpd, get_weather_by_time
from services import send_telegram_message, get_quick_solution
from analytics import analyze_day_by_blocks_rt, predict_vpd_trend_v3
from charts import draw_vpd_chart, draw_temp_humidity_combo_chart

# Cấu hình trang
st.set_page_config(page_title="VPD Farm Analytics", page_icon="🌿", layout="wide")

# --- CSS CUSTOM ĐỂ GIỐNG ẢNH MẪU ---
st.markdown("""
    <style>
    /* Tổng thể */
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; }
    
    /* Card chỉ số lớn (VPD) */
    .vpd-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .vpd-value {
        font-size: 48px;
        font-weight: bold;
        color: #2E7D32;
        margin: 10px 0;
    }
    
    /* Box thông báo giải pháp */
    .solution-box {
        padding: 15px;
        border-radius: 8px;
        font-weight: bold;
        margin-top: 10px;
        border-left: 5px solid;
    }
    .solution-wet { background-color: #E3F2FD; border-left-color: #2196F3; color: #0D47A1; }
    .solution-dry { background-color: #FFEBEE; border-left-color: #F44336; color: #B71C1C; }
    .solution-ideal { background-color: #E8F5E9; border-left-color: #4CAF50; color: #1B5E20; }

    /* Header các mục */
    .section-header {
        color: #1A5276;
        font-weight: bold;
        border-bottom: 2px solid #D4E6F1;
        padding-bottom: 5px;
        margin-bottom: 15px;
        font-size: 16px;
        display: flex;
        align-items: center;
    }
    
    /* Bảng */
    .styled-table { font-size: 13px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- KHỞI TẠO SESSION STATE CHUẨN ---
DANH_SACH_CAY = {
    "🍓 Dâu tây Đà Lạt (Hoa / Trái)": {"Sang": (0.6, 0.9), "Trua": (0.8, 1.2), "Chieu": (0.7, 1.0), "Dem": (0.4, 0.7)},
    "🛠️ Tùy chỉnh thủ công ngưỡng riêng": {"Sang": (0.6, 1.1), "Trua": (0.8, 1.4), "Chieu": (0.7, 1.2), "Dem": (0.5, 0.9)}
}

default_states = {
    "temp": 24.0, "rh": 75.0, "countdown": 15, "is_running": False,
    "history": [], "stt_counter": 0, "plant_idx": 0,
    "h_sang": 5, "h_trua": 10, "h_chieu": 15, "h_dem": 19,
    "simulated_time": "2026-05-24 07:00:00",
    "custom_thresholds": {"Sang": (0.6, 0.9), "Trua": (0.8, 1.2), "Chieu": (0.7, 1.0), "Dem": (0.4, 0.7)}
}

for key, value in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- LOGIC HỖ TRỢ ---
def get_current_thresholds(hour):
    plant_name = list(DANH_SACH_CAY.keys())[st.session_state.plant_idx]
    if plant_name == "🛠️ Tùy chỉnh thủ công ngưỡng riêng":
        if st.session_state.h_sang <= hour < st.session_state.h_trua: return st.session_state.custom_thresholds["Sang"]
        if st.session_state.h_trua <= hour < st.session_state.h_chieu: return st.session_state.custom_thresholds["Trua"]
        if st.session_state.h_chieu <= hour < st.session_state.h_dem: return st.session_state.custom_thresholds["Chieu"]
        return st.session_state.custom_thresholds["Dem"]
    else:
        if st.session_state.h_sang <= hour < st.session_state.h_trua: return DANH_SACH_CAY[plant_name]["Sang"]
        if st.session_state.h_trua <= hour < st.session_state.h_chieu: return DANH_SACH_CAY[plant_name]["Trua"]
        if st.session_state.h_chieu <= hour < st.session_state.h_dem: return DANH_SACH_CAY[plant_name]["Chieu"]
        return DANH_SACH_CAY[plant_name]["Dem"]

def trigger_new_data():
    cur_sim = datetime.strptime(st.session_state.simulated_time, "%Y-%m-%d %H:%M:%S")
    st.session_state.temp, st.session_state.rh = get_weather_by_time(cur_sim)
    st.session_state.countdown = 15
    st.session_state.stt_counter += 1
    
    vpd = calculate_vpd(st.session_state.temp, st.session_state.rh)
    v_min, v_max = get_current_thresholds(cur_sim.hour)
    
    status = "✅ Lý tưởng"
    if vpd < v_min: status = "⚠️ Quá ẩm"
    elif vpd > v_max: status = "🚨 Quá khô"
    
    st.session_state.history.insert(0, {
        "STT": st.session_state.stt_counter,
        "Ngày": cur_sim.strftime("Ngày %d/%m"),
        "Thời gian": cur_sim.strftime("%H:%M"),
        "datetime_internal": cur_sim,
        "Nhiệt độ (°C)": st.session_state.temp,
        "Độ ẩm (%)": st.session_state.rh,
        "VPD (kPa)": round(vpd, 2),
        "Trạng thái": status,
        "V_Min": v_min, "V_Max": v_max
    })
    st.session_state.simulated_time = (cur_sim + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

# --- GIAO DIỆN CHÍNH (2 CỘT) ---
col_sidebar, col_main = st.columns([1, 2.5])

# --- CỘT TRÁI: CẤU HÌNH ---
with col_sidebar:
    st.markdown("<div class='section-header'>🌿 CẤU HÌNH LOẠI CÂY TRỒNG</div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.session_state.plant_idx = st.selectbox("Mô hình cây trồng:", range(len(DANH_SACH_CAY)), 
                                                  format_func=lambda x: list(DANH_SACH_CAY.keys())[x])
        
        st.markdown("**Khung thời gian các buổi:**")
        st.session_state.h_sang = st.slider("Sáng bắt đầu từ (h):", 4, 7, st.session_state.h_sang)
        st.session_state.h_trua = st.slider("Trưa bắt đầu từ (h):", 10, 12, st.session_state.h_trua)
        st.session_state.h_chieu = st.slider("Chiều bắt đầu từ (h):", 14, 16, st.session_state.h_chieu)
        st.session_state.h_dem = st.slider("Đêm bắt đầu từ (h):", 18, 21, st.session_state.h_dem)

    st.markdown("<div class='section-header'>🎯 NGƯỠNG VPD THEO BUỔI</div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.session_state.custom_thresholds["Sang"] = st.slider("Sáng (kPa):", 0.0, 2.0, st.session_state.custom_thresholds["Sang"], 0.1)
        st.session_state.custom_thresholds["Trua"] = st.slider("Trưa (kPa):", 0.0, 2.0, st.session_state.custom_thresholds["Trua"], 0.1)
        st.session_state.custom_thresholds["Chieu"] = st.slider("Chiều (kPa):", 0.0, 2.0, st.session_state.custom_thresholds["Chieu"], 0.1)
        st.session_state.custom_thresholds["Dem"] = st.slider("Đêm (kPa):", 0.0, 2.0, st.session_state.custom_thresholds["Dem"], 0.1)

    st.markdown("<div class='section-header'>🤖 ĐIỀU KHIỂN</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("▶️ Bắt đầu", type="primary"): st.session_state.is_running = True
    if c2.button("⏸️ Tạm dừng"): st.session_state.is_running = False
    if st.button("🗑️ Reset All"): 
        st.session_state.history = []
        st.rerun()

    @st.fragment(run_every=1)
    def update_logic():
        if st.session_state.is_running:
            st.session_state.countdown -= 1
            if st.session_state.countdown <= 0:
                trigger_new_data()
                st.rerun()

    update_logic()

    st.markdown("<div class='section-header'>📊 THÔNG SỐ HIỆN TẠI</div>", unsafe_allow_html=True)
    with st.container(border=True):
        cur_sim_dt = datetime.strptime(st.session_state.simulated_time, "%Y-%m-%d %H:%M:%S")
        st.markdown(f"**Thời gian:** `{cur_sim_dt.strftime('%H:%M')} - {cur_sim_dt.strftime('%d/%m')}`")
        
        c_temp, c_rh = st.columns(2)
        c_temp.metric("🌡️ Nhiệt độ", f"{st.session_state.temp}°C")
        c_rh.metric("💧 Độ ẩm", f"{st.session_state.rh}%")
        
        vpd_now = calculate_vpd(st.session_state.temp, st.session_state.rh)
        v_min, v_max = get_current_thresholds(cur_sim_dt.hour)
        
        st.markdown(f"""
            <div class="vpd-card">
                <div style="font-size:14px; color:#666;">CHỈ SỐ VPD THỰC TẾ</div>
                <div class="vpd-value">{vpd_now:.2f} kPa</div>
            </div>
        """, unsafe_allow_html=True)

        if vpd_now < v_min:
            st.markdown(f"<div class='solution-box solution-wet'>🟦 Stress Ẩm: {get_quick_solution(vpd_now, v_min, v_max, cur_sim_dt.hour)}</div>", unsafe_allow_html=True)
        elif vpd_now > v_max:
            st.markdown(f"<div class='solution-box solution-dry'>🟥 Stress Khô: {get_quick_solution(vpd_now, v_min, v_max, cur_sim_dt.hour)}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='solution-box solution-ideal'>🟩 Lý tưởng: {get_quick_solution(vpd_now, v_min, v_max, cur_sim_dt.hour)}</div>", unsafe_allow_html=True)

# --- CỘT PHẢI: BIỂU ĐỒ & BẢNG BIỂU ---
with col_main:
    st.markdown("<div class='section-header'>📈 PHÂN TÍCH DIỄN BIẾN CHU KỲ PHÒNG DỊCH</div>", unsafe_allow_html=True)
    
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        df_display = df.sort_values("datetime_internal")
        
        v_min_avg = df["V_Min"].mean()
        v_max_avg = df["V_Max"].mean()
        st.altair_chart(draw_vpd_chart(df_display, v_min_avg, v_max_avg), use_container_width=True)
        
        st.markdown("<div class='section-header'>📊 BẢNG ĐÁNH GIÁ CHUNG THEO BUỔI</div>", unsafe_allow_html=True)
        summary_df = analyze_day_by_blocks_rt(st.session_state.history, v_min_avg, v_max_avg, df["Ngày"].iloc[0])
        st.table(summary_df)

        st.markdown("<div class='section-header'>📋 NHẬT KÝ CHI TIẾT ĐIỂM DỮ LIỆU</div>", unsafe_allow_html=True)
        st.dataframe(df[["STT", "Thời gian", "Nhiệt độ (°C)", "Độ ẩm (%)", "VPD (kPa)", "Trạng thái"]], use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có dữ liệu mô phỏng. Nhấn 'Bắt đầu' để bắt đầu chu kỳ.")

# --- FOOTER CẢNH BÁO ---
if st.session_state.history:
    last_vpd = st.session_state.history[0]["VPD (kPa)"]
    v_min, v_max = st.session_state.history[0]["V_Min"], st.session_state.history[0]["V_Max"]
    
    if last_vpd < v_min or last_vpd > v_max:
        st.markdown(f"""
            <div style="position: fixed; bottom: 0; left: 0; width: 100%; background-color: #fce4ec; border-top: 3px solid #e91e63; padding: 10px; z-index: 1000; text-align: center;">
                <b style="color: #c2185b;">⚠️ KHUYẾN NGHỊ ĐIỀU KHIỂN PHẦN CỨNG LẬP TỨC:</b> 
                Dựa trên VPD {last_vpd} kPa, hãy {get_quick_solution(last_vpd, v_min, v_max, datetime.now().hour)}
            </div>
        """, unsafe_allow_html=True)
