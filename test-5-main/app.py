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
        draw_temperature_chart, \
        draw_humidity_chart, \
        draw_vpd_chart
    )
except ModuleNotFoundError as e:
    st.error(f"❌ Không tìm thấy module bổ trợ: {e.name}")
    st.stop()

# --- CẤU HÌNH BAN ĐẦU ---\nst.set_page_config(page_title="VPD Farm Analytics", page_icon="🌿", layout="wide")

DANH_SACH_CAY = {
    "🍓 Dâu tây Đà Lạt (Hoa / Trái)": (0.6, 1.1),
    "🍓 Dâu tây Đà Lạt (Giai đoạn ngó/cây con)": (0.4, 0.8),
    "🌹 Hoa hồng nhà kính (Đà Lạt)": (0.8, 1.3),
    "🌼 Hoa cúc / Hoa đồng tiền": (0.7, 1.2),
    "🍅 Cà chua bi / 🫑 Ớt chuông công nghệ cao": (0.8, 1.4),
    "🥬 Rau xà lách thủy canh / Rau ăn lá": (0.5, 0.9),
    "🧪 Cấu hình tùy chỉnh thủ công (Custom)": (0.0, 3.0)
}

# --- KHỞI TẠO STATE ---
if "history_data" not in st.session_state:
    st.session_state.history_data = []
if "sim_time" not in st.session_state:
    st.session_state.sim_time = datetime.now() - timedelta(hours=6)
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# --- SIDEBAR: ĐIỀU KHIỂN & CẤU HÌNH ---
st.sidebar.title("🎮 Hệ Thống Cấu Hình")

cay_selected = st.sidebar.selectbox("🎯 Chọn loại cây trồng:", list(DANH_SACH_CAY.keys()))
vpd_min_def, vpd_max_def = DANH_SACH_CAY[cay_selected]

if cay_selected == "🧪 Cấu hình tùy chỉnh thủ công (Custom)":
    vpd_min = st.sidebar.slider("Biên dưới VPD Lý Tưởng (kPa)", 0.1, 2.5, 0.6, 0.1)
    vpd_max = st.sidebar.slider("Biên trên VPD Lý Tưởng (kPa)", 0.2, 3.0, 1.2, 0.1)
else:
    vpd_min, vpd_max = vpd_min_def, vpd_max_def
    st.sidebar.info(f"📊 Ngưỡng VPD khuyến nghị:\n**{vpd_min} kPa - {vpd_max} kPa**")

# --- CẤU HÌNH NHẬN THÔNG BÁO TELEGRAM ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔔 Cấu hình Nhận Thông Báo")
tele_token = st.sidebar.text_input(
    "Telegram Bot Token", 
    value="8917951413:AAE6LKUEfYEYiQrFWGoKsQn0tumZc_XbcHg", 
    type="password"
)
tele_chat_id = st.sidebar.text_input(
    "Telegram Chat ID", 
    value="7290661009"
)

# Điều khiển luồng thời gian thực
st.sidebar.markdown("---")
col_btn1, col_btn2 = st.sidebar.columns(2)
if col_btn1.button("▶️ Bắt đầu chạy", use_container_width=True):
    st.session_state.is_running = True
if col_btn2.button("⏸️ Tạm dừng", use_container_width=True):
    st.session_state.is_running = False

if st.sidebar.button("🗑️ Reset dữ liệu", use_container_width=True):
    st.session_state.history_data = []
    st.session_state.sim_time = datetime.now() - timedelta(hours=6)
    st.rerun()

# --- CHẠY VÒNG LẶP THỜI GIAN THỰC (REAL-TIME SIMULATION) ---
if st.session_state.is_running:
    st.session_state.sim_time += timedelta(minutes=15)
    cur_t, cur_h = get_weather_by_time(st.session_state.sim_time)
    cur_v = round(calculate_vpd(cur_t, cur_h), 2)
    
    # Xác định trạng thái
    if cur_v < vpd_min:
        status = "🟦 Quá ẩm"
    elif cur_v > vpd_max:
        status = "🟥 Quá khô"
    else:
        status = "🟩 Lý tưởng"

    # Tạo object log mới
    new_log = {
        "datetime_internal": st.session_state.sim_time,
        "Hiển thị Giờ": st.session_state.sim_time.strftime("%H:%M"),
        "Nhiệt độ (°C)": cur_t,
        "Độ ẩm (%)": cur_h,
        "VPD (kPa)": cur_v,
        "Trạng thái": status
    }
    
    # Chèn lên đầu danh sách lịch sử
    st.session_state.history_data.insert(0, new_log)
    if len(st.session_state.history_data) > 48:
        st.session_state.history_data.pop()

    # BẮN CẢNH BÁO TELEGRAM KHI VƯỢT NGƯỠNG
    if status != "🟩 Lý tưởng":
        giai_phap = get_quick_solution(cur_v, vpd_min, vpd_max, st.session_state.sim_time.hour)
        message_content = (
            f"⚠️ **CẢNH BÁO VI KHÍ HẬU FARM**\n"
            f"⏰ Thời gian: {new_log['Hiển thị Giờ']}\n"
            f"🌱 Cây trồng: {cay_selected}\n"
            f"🌡️ Nhiệt độ: {cur_t}°C | 💧 Độ ẩm: {cur_h}%\n"
            f"📊 Chỉ số VPD hiện tại: **{cur_v} kPa** ({status})\n"
            f"🎯 Ngưỡng an toàn: {vpd_min} - {vpd_max} kPa\n"
            f"💡 **Giải pháp nhanh:** {giai_phap}"
        )
        # Thực hiện gọi hàm gửi qua Telegram Bot thay vì Discord
        success = send_telegram_message(tele_token, tele_chat_id, message_content)
        if success:
            st.sidebar.success(f"✅ Đã bắn Telegram lúc {new_log['Hiển thị Giờ']}")
        else:
            st.sidebar.error("❌ Gửi thông báo lỗi. Kiểm tra Token/ID!")

# --- GIAO DIỆN HIỂN THỊ CHÍNH (MAIN DASHBOARD) ---
st.title("🌿 VPD Farm Analytics - Hệ Thống Giám Sát Thời Gian Thực")
st.markdown("Hệ thống tự động mô phỏng môi trường nhà kính Đà Lạt và phát hiện rủi ro sinh trưởng qua chỉ số VPD.")

# Chuyển đổi list thành Dataframe phục vụ vẽ đồ thị
df_display = pd.DataFrame(st.session_state.history_data)

if not df_display.empty:
    # Bản sao xử lý số liệu gốc không bị đảo ngược khi hiển thị đồ thị
    df_chart_flow = df_display.iloc[::-1].copy() if len(df_display) > 1 else df_display.copy()
    
    # Khu vực Widget Chỉ số tức thời (Metric)
    latest = df_display.iloc[0]
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("⏰ Thời Gian Mô Phỏng", latest["Hiển thị Giờ"])
    m_col2.metric("🌡️ Nhiệt Độ Hiện Tại", f"{latest['Nhiệt độ (°C)']} °C")
    m_col3.metric("💧 Độ Ẩm Không Khí", f"{latest['Độ ẩm (%)']} %")
    m_col4.metric("📊 Chỉ Số VPD Hiện Tại", f"{latest['VPD (kPa)']} kPa", delta=latest["Trạng thái"])

    # Khu vực phân tích Xu hướng bằng AI/Thuật toán nâng cao
    st.markdown("### 🧠 Phân Tích Xu Hướng & Dự Báo (Thuật Toán v3)")
    xu_huong_text, xu_huong_code = predict_vpd_trend_v3(
        st.session_state.history_data, 
        st.session_state.sim_time.hour, 
        vpd_min, 
        vpd_max
    )
    if xu_huong_code == "alarm_high":
        st.error(xu_huong_text)
    elif xu_huong_code == "alarm_low":
        st.warning(xu_huong_text)
    else:
        st.info(xu_huong_text)

    # Đồ thị trực quan hoá
    st.markdown("### 📈 Biểu Đồ Diễn Biến Vi Khí Hậu Theo Chu Kỳ")
    g_col1, g_col2, g_col3 = st.columns(3)
    with g_col1:
        st.markdown("<center><b>Đồ thị Nhiệt độ</b></center>", unsafe_allow_html=True)
        st.altair_chart(draw_temperature_chart(df_chart_flow), use_container_width=True)
    with g_col2:
        st.markdown("<center><b>Đồ thị Độ ẩm</b></center>", unsafe_allow_html=True)
        st.altair_chart(draw_humidity_chart(df_chart_flow), use_container_width=True)
    with g_col3:
        st.markdown("<center><b>Đồ thị phân vùng an toàn VPD (Vùng xanh là lý tưởng)</b></center>", unsafe_allow_html=True)
        st.altair_chart(draw_vpd_chart(df_chart_flow, vpd_min, vpd_max), use_container_width=True)

    # Thống kê phân tích sâu
    st.markdown("### 📊 Thống Kê & Đánh Giá Rủi Rô")
    s_col1, s_col2 = st.columns([1, 1])
    
    with s_col1:
        st.markdown("##### ⏳ Thời Gian Cây Bị Stress Tích Lũy")
        stress_report = calculate_plant_stress_hours(st.session_state.history_data)
        st.write(f"- Tổng số giờ dữ liệu đã quét: **{stress_report['total_hours']:.2f} giờ**")
        st.write(f"- 🟦 Thời gian quá ẩm (VPD thấp): <font color='#1976D2'><b>{stress_report['low_stress_hours']:.2f} giờ</b></font> ({stress_report['low_stress_pct']:.1f}%)", unsafe_allow_html=True)
        st.write(f"- 🟥 Thời gian quá khô (VPD cao): <font color='#D32F2F'><b>{stress_report['high_stress_hours']:.2f} giờ</b></font> ({stress_report['high_stress_pct']:.1f}%)", unsafe_allow_html=True)
        st.write(f"- 🟩 Thời gian sinh trưởng hoàn hảo: <font color='#388E3C'><b>{stress_report['optimal_hours']:.2f} giờ</b></font> ({stress_report['optimal_pct']:.1f}%)", unsafe_allow_html=True)

    with s_col2:
        st.markdown("##### 📝 Nhật Ký Theo Dõi Log Mới Nhất")
        st.dataframe(df_display[["Hiển thị Giờ", "Nhiệt độ (°C)", "Độ ẩm (%)", "VPD (kPa)", "Trạng thái"]].head(10), use_container_width=True)

    # --- BÁO CÁO THEO BUỔI ---
    st.markdown("---")
    st.markdown("##### 📊 BÁO CÁO PHÂN TÍCH TỔNG HỢP THEO BUỔI CHU KỲ (Dữ liệu gốc)")
    df_f_blk = df_display.copy()
    if len(df_f_blk) > 0:
        df_f_blk["Hour"] = df_f_blk["datetime_internal"].dt.hour
        def b_assign(h):
            if 5 <= h < 10: return "🌅 Sáng (05h - 10h)"
            if 10 <= h < 15: return "☀️ Trưa (10h - 15h)"
            if 15 <= h < 19: return "🌇 Chiều (15h - 19h)"
            if 19 <= h < 23: return "🌌 Tối (19h - 23h)"
            return "🌙 Khuya (23h - 05h)"
        df_f_blk["Buổi"] = df_f_blk["Hour"].apply(b_assign)
        
        # Tạo bản sao VPD làm dữ liệu thô gốc cho phân tích chu kỳ
        df_f_blk["VPD_raw"] = df_f_blk["VPD (kPa)"]
        b_sum = df_f_blk.groupby("Buổi").agg({"Nhiệt độ (°C)": "mean", "Độ ẩm (%)": "mean", "VPD_raw": "mean"}).reindex(["🌅 Sáng (05h - 10h)", "☀️ Trưa (10h - 15h)", "🌇 Chiều (15h - 19h)", "🌌 Tối (19h - 23h)", "🌙 Khuya (23h - 05h)"]).dropna()
        
        for idx, row in b_sum.iterrows():
            avg_t = round(row["Nhiệt độ (°C)"], 1)
            avg_h = round(row["Độ ẩm (%)"], 1)
            avg_v = round(row["VPD_raw"], 2)
            if avg_v < vpd_min:
                st.write(f"- **{idx}**: Trung bình có Nhiệt độ: {avg_t}°C, Độ ẩm: {avg_h}%, VPD: {avg_v} kPa -> 🟦 *Khí hậu buổi này quá ẩm, chú ý kiểm tra nấm bệnh.*")
            elif avg_v > vpd_max:
                st.write(f"- **{idx}**: Trung bình có Nhiệt độ: {avg_t}°C, Độ ẩm: {avg_h}%, VPD: {avg_v} kPa -> 🟥 *Khí hậu buổi này bị hanh khô, cây dễ héo rũ.*")
            else:
                st.write(f"- **{idx}**: Trung bình có Nhiệt độ: {avg_t}°C, Độ ẩm: {avg_h}%, VPD: {avg_v} kPa -> 🟩 *Môi trường tối ưu tuyệt vời cho quang hợp.*")

else:
    st.info("💡 Hãy nhấn nút 'Bắt đầu chạy' ở thanh bên để hệ thống kích hoạt thu thập và phân tích dữ liệu.")

# Tự động reload ứng dụng sau mỗi 2.5 giây khi đang kích hoạt real-time
if st.session_state.is_running:
    import time
    time.sleep(2.5)
    st.rerun()
