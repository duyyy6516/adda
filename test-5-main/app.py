import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import sys
import os

# Tự động tìm kiếm module ở thư mục hiện tại
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
    "🍅 Cà chua bi": (0.8, 1.4)
}

st.title("🌿 Hệ Thống Giám Sát & Dự Báo VPD Farm Thời Gian Thực")
st.markdown("---")

# --- SIDEBAR: CẤU HÌNH HỆ THỐNG ---
st.sidebar.header("⚙️ CẤU HÌNH HỆ THỐNG")

# 1. Chọn loại cây
ten_cay = st.sidebar.selectbox("Chọn loại cây trồng hiện tại:", list(DANH_SACH_CAY.keys()))
vpd_min, vpd_max = DANH_SACH_CAY[ten_cay]

st.sidebar.info(f"**Biên độ VPD lý tưởng:** {vpd_min} - {vpd_max} kPa")

# 2. Cấu hình kết nối Telegram Bot (Đã điền sẵn thông tin của bạn)
st.sidebar.markdown("---")
st.sidebar.header("🤖 CẤU HÌNH TELEGRAM BOT")
tele_token = st.sidebar.text_input(
    "Telegram Bot Token:", 
    value="8917951413:AAE6LKUEfYEYiQrFWGoKsQn0tumZc_XbcHg", 
    type="password"
)
tele_chat_id = st.sidebar.text_input(
    "Telegram Chat ID:", 
    value="7290661009"
)

# Khởi tạo trạng thái phiên lưu trữ lịch sử
if "history_data" not in st.session_state:
    st.session_state.history_data = []

# --- PHẦN XỬ LÝ DỮ LIỆU THỜI GIAN THỰC (SIMULATION) ---
col1, col2, col3 = st.columns(3)

# Lấy mốc thời gian thực hiện tại
now = datetime.now()
temp, rh = get_weather_by_time(now)
vpd = round(calculate_vpd(temp, rh), 2)

with col1:
    st.metric("🌡️ Nhiệt độ Hiện Tại", f"{temp} °C")
with col2:
    st.metric("💧 Độ ẩm Hiện Tại", f"{rh} %")
with col3:
    st.metric("📊 Chỉ số VPD Hiện Tại", f"{vpd} kPa")

# Thêm bản ghi mới vào lịch sử điều phối
current_record = {
    "Hiển thị Giờ": now.strftime("%H:%M:%S"),
    "Nhiệt độ (°C)": temp,
    "Độ ẩm (%)": rh,
    "VPD (kPa)": vpd,
    "datetime_internal": now
}

# Đẩy lên đầu danh sách lịch sử
st.session_state.history_data.insert(0, current_record)
if len(st.session_state.history_data) > 30:
    st.session_state.history_data.pop()

# --- PHÂN TÍCH VÀ CẢNH BÁO ---
st.markdown("---")
st.markdown("##### 🚨 ĐÁNH GIÁ XU HƯỚNG & HÀNH ĐỘNG KHẨN CẤP")

trend_msg, status_type = predict_vpd_trend_v3(st.session_state.history_data, now.hour, vpd_min, vpd_max)

if status_type == "danger":
    st.error(trend_msg)
    # Trigger gửi tin nhắn tự động qua Telegram khi xảy ra bất thường khẩn cấp
    if tele_token and tele_chat_id:
        solution = get_quick_solution(vpd, vpd_min, vpd_max, now.hour)
        alert_content = (
            f"⚠️ **CẢNH BÁO VPD FARM** ⚠️\n\n"
            f"- **Loại cây**: {ten_cay}\n"
            f"- **Chỉ số hiện tại**: {vpd} kPa\n"
            f"- **Trạng thái**: {trend_msg}\n\n"
            f"👉 **Giải pháp**: {solution}"
        )
        success = send_telegram_message(tele_token, tele_chat_id, alert_content)
        if success:
            st.toast("🚀 Đã bắn thông báo khẩn cấp tới Telegram của bạn!", icon="🤖")
        else:
            st.toast("❌ Lỗi gửi tin nhắn Telegram, hãy kiểm tra lại Token/Chat ID", icon="🚨")
elif status_type == "warning":
    st.warning(trend_msg)
else:
    st.success(trend_msg)

# --- VẼ BIỂU ĐỒ ---
st.markdown("---")
st.markdown("##### 📈 ĐỒ THỊ BIẾN THIÊN CHU KỲ GẦN NHẤT")
df_chart = pd.DataFrame(st.session_state.history_data).iloc[::-1] # Đảo thứ tự xuôi dòng thời gian

if not df_chart.empty:
    df_chart['Trạng thái'] = df_chart['VPD (kPa)'].apply(lambda x: 'Lý tưởng' if vpd_min <= x <= vpd_max else ('Quá ẩm' if x < vpd_min else 'Quá khô'))
    
    c_vpd = draw_vpd_chart(df_chart, vpd_min, vpd_max)
    c_temp = draw_temperature_chart(df_chart)
    c_rh = draw_humidity_chart(df_chart)
    
    st.altair_chart(c_vpd, use_container_width=True)
    
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1:
        st.altair_chart(c_temp, use_container_width=True)
    with sub_col2:
        st.altair_chart(c_rh, use_container_width=True)

# --- BÁO CÁO THEO BUỔI ---
st.markdown("---")
st.markdown("##### 📊 BÁO CÁO PHÂN TÍCH TỔNG HỢP THEO BUỔI CHU KỲ (Dữ liệu gốc)")
if len(df_chart) > 0:
    df_chart["Hour"] = df_chart["datetime_internal"].dt.hour
    def b_assign(h):
        if 5 <= h < 10: return "🌅 Sáng (05h - 10h)"
        if 10 <= h < 15: return "☀️ Trưa (10h - 15h)"
        if 15 <= h < 19: return "🌇 Chiều (15h - 19h)"
        if 19 <= h < 23: return "🌌 Tối (19h - 23h)"
        return "🌙 Khuya (23h - 05h)"
    df_chart["Buổi"] = df_chart["Hour"].apply(b_assign)
    
    b_sum = df_chart.groupby("Buổi").agg({"Nhiệt độ (°C)": "mean", "Độ ẩm (%)": "mean", "VPD (kPa)": "mean"}).reindex(["🌅 Sáng (05h - 10h)", "☀️ Trưa (10h - 15h)", "🌇 Chiều (15h - 19h)", "🌌 Tối (19h - 23h)", "🌙 Khuya (23h - 05h)"]).dropna()
    st.dataframe(b_sum.round(2), use_container_width=True)
