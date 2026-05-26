import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import sys
import os

# Tự động tìm kiếm module ở thư mục hiện tại để tránh lỗi import chéo
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import các module nội bộ với xử lý ngoại lệ chặt chẽ
try:
    from calculations import calculate_vpd, get_weather_by_time
    from services import send_telegram_message, get_quick_solution
    from analytics import (
        analyze_day_by_blocks_rt, 
        predict_vpd_trend_v3, 
        calculate_plant_stress_hours
    )
    from charts import (
        draw_combined_temp_humidity_chart, 
        draw_vpd_chart
    )
except ModuleNotFoundError as e:
    st.error(f"❌ Không tìm thấy module bổ trợ: {e.name}. Vui lòng kiểm tra lại cấu trúc file dự án!")
    st.stop()

# --- CẤU HÌNH GIAO DIỆN BAN ĐẦU ---
st.set_page_config(page_title="VPD Farm Analytics", page_icon="🌿", layout="wide")

# Danh sách các loại cây trồng phổ biến tại Đà Lạt và ngưỡng VPD tiêu chuẩn (kPa)
DANH_SACH_CAY = {
    "🍓 Dâu tây Đà Lạt (Hoa / Trái)": (0.6, 1.1),
    "🍓 Dâu tây Đà Lạt (Giai đoạn ngó/cây con)": (0.4, 0.8),
    "🌹 Hoa hồng nhà kính (Đà Lạt)": (0.8, 1.3),
    "🌼 Hoa cúc / Hoa đồng tiền": (0.7, 1.2),
    "🍅 Cà chua bi / Ớt chuông công nghệ cao": (0.8, 1.4),
    "🥬 Rau thủy canh (Xà lách, cải kale...)": (0.5, 1.0)
}

st.title("🌿 Hệ Thống Giám Sát Vi Khí Hậu & Quản Lý Chỉ Số VPD Real-Time")
st.caption("Ứng dụng phân tích dữ liệu, tính toán Áp suất hơi thâm hụt (VPD) và dự báo xu hướng stress cho nông nghiệp công nghệ cao Đà Lạt")

# --- THANH ĐIỀU KHIỂN CẤU HÌNH (SIDEBAR) ---
st.sidebar.header("⚙️ Cấu Hình Hệ Thống Farm")

# 1. Chọn loại cây để áp ngưỡng tối ưu tự động
cay_selected = st.sidebar.selectbox("1. Chọn loại cây trồng cần giám sát:", list(DANH_SACH_CAY.keys()))
min_vpd_init, max_vpd_init = DANH_SACH_CAY[cay_selected]

# Cho phép tùy chỉnh thủ công tinh chỉnh dải biên an toàn
vpd_min = st.sidebar.slider("Ngưỡng VPD Dưới An Toàn (kPa):", 0.1, 2.0, min_vpd_init, 0.1)
vpd_max = st.sidebar.slider("Ngưỡng VPD Trên An Toàn (kPa):", 0.5, 3.0, max_vpd_init, 0.1)

# 2. Cấu hình Telegram Alerts
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Cấu hình Cảnh báo Telegram")
enable_tg = st.sidebar.checkbox("Bật cảnh báo tự động", value=False)
tg_token = st.sidebar.text_input("Telegram Bot Token:", value="", type="password")
tg_chat_id = st.sidebar.text_input("Telegram Chat ID:", value="")

# 3. Quản lý trạng thái lưu trữ phiên dữ liệu mô phỏng (Session State)
if "simulation_data" not in st.session_state:
    st.session_state.simulation_data = []
if "last_sim_time" not in st.session_state:
    st.session_state.last_sim_time = datetime.now() - timedelta(hours=24) # Giả lập sẵn 24h trước

# Nút dọn dẹp bộ nhớ/Khởi động lại chu kỳ
if st.sidebar.button("🗑️ Xóa & Khởi tạo lại dữ liệu"):
    st.session_state.simulation_data = []
    st.session_state.last_sim_time = datetime.now() - timedelta(hours=24)
    st.rerun()

# --- LUỒNG TỰ ĐỘNG SINH DỮ LIỆU ĐỂ GIẢ LẬP REAL-TIME ---
# Sinh dữ liệu nếu hệ thống chưa có dữ liệu quá khứ
if len(st.session_state.simulation_data) == 0:
    current_step_time = st.session_state.last_sim_time
    now_time = datetime.now()
    
    # Sinh tuần tự các mốc cách nhau 30 phút để vẽ biểu đồ
    while current_step_time < now_time:
        temp, rh = get_weather_by_time(current_step_time)
        vpd_val = calculate_vpd(temp, rh)
        
        # Đánh giá trạng thái
        if vpd_val < vpd_min:
            status = "🟦 Quá ẩm (Dưới biên)"
        elif vpd_val > vpd_max:
            status = "🟥 Quá khô (Vượt biên)"
        else:
            status = "🟩 Lý tưởng (An toàn)"
            
        st.session_state.simulation_data.append({
            "datetime_internal": current_step_time,
            "Hiển thị Giờ": current_step_time.strftime("%H:%M"),
            "Nhiệt độ (°C)": temp,
            "Độ ẩm (%)": rh,
            "VPD (kPa)": round(vpd_val, 2),
            "VPD_raw": vpd_val,
            "Trạng thái": status
        })
        current_step_time += timedelta(minutes=30)
    st.session_state.last_sim_time = now_time

# --- CẬP NHẬT ĐIỂM DỮ LIỆU REAL-TIME MỚI NHẤT ---
# Mỗi lần F5 trang hoặc bấm nút, hệ thống sinh ra 1 điểm dữ liệu thời gian thực hiện tại
now_rt = datetime.now()
if now_rt - st.session_state.last_sim_time >= timedelta(minutes=1):
    temp_rt, rh_rt = get_weather_by_time(now_rt)
    vpd_rt = calculate_vpd(temp_rt, rh_rt)
    
    if vpd_rt < vpd_min:
        status_rt = "🟦 Quá ẩm (Dưới biên)"
    elif vpd_rt > vpd_max:
        status_rt = "🟥 Quá khô (Vượt biên)"
    else:
        status_rt = "🟩 Lý tưởng (An toàn)"
        
    st.session_state.simulation_data.append({
        "datetime_internal": now_rt,
        "Hiển thị Giờ": now_rt.strftime("%H:%M"),
        "Nhiệt độ (°C)": temp_rt,
        "Độ ẩm (%)": rh_rt,
        "VPD (kPa)": round(vpd_rt, 2),
        "VPD_raw": vpd_rt,
        "Trạng thái": status_rt
    })
    st.session_state.last_sim_time = now_rt

# Giới hạn giữ lại tối đa 48 bản ghi gần nhất để tránh tràn RAM giao diện
if len(st.session_state.simulation_data) > 48:
    st.session_state.simulation_data = st.session_state.simulation_data[-48:]

# Chuyển đổi dữ liệu sang Pandas DataFrame để xử lý thuật toán và hiển thị
df_display = pd.DataFrame(st.session_state.simulation_data)
latest_entry = st.session_state.simulation_data[-1]

# --- HIỂN THỊ CHỈ SỐ TIÊU ĐIỂM THỜI GIAN THỰC (METRICS CARD) ---
st.subheader(f"📍 Hiện trạng nhà kính: {cay_selected}")

m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric(label="🌡️ Nhiệt độ Hiện Tại", value=f"{latest_entry['Nhiệt độ (°C)']} °C")
with m_col2:
    st.metric(label="💧 Độ ẩm Hiện Tại", value=f"{latest_entry['Độ ẩm (%)']} %")
with m_col3:
    # Đổi màu hiển thị số dựa theo trạng thái an toàn hay stress
    if "Lý tưởng" in latest_entry["Trạng thái"]:
        st.metric(label="📉 Chỉ số VPD Hiện Tại", value=f"{latest_entry['VPD (kPa)']} kPa", delta="🟩 AN TOÀN")
    else:
        st.metric(label="📉 Chỉ số VPD Hiện Tại", value=f"{latest_entry['VPD (kPa)']} kPa", delta="⚠️ NGUY HIỂM", delta_color="inverse")
with m_col4:
    st.metric(label="🕒 Mốc cập nhật cuối", value=latest_entry["Hiển thị Giờ"])

# --- THUẬT TOÁN DỰ BÁO XU HƯỚNG VÀ PHÁT HIỆN LỖI (ANALYTICS) ---
st.markdown("---")
# Đảo ngược danh sách dữ liệu cho đúng cấu trúc hàm dự báo (mới nhất đứng đầu)
history_reversed = list(reversed(st.session_state.simulation_data))
trend_msg, trend_code = predict_vpd_trend_v3(history_reversed, now_rt.hour, vpd_min, vpd_max)

# Hiển thị hộp cảnh báo thông minh dựa trên trend_code trả về
if trend_code == "danger_dry":
    st.error(f"🔴 **XU HƯỚNG NGUY HIỂM:** {trend_msg}")
elif trend_code == "danger_humid":
    st.warning(f"🔵 **XU HƯỚNG NGUY HIỂM:** {trend_msg}")
elif trend_code == "sensor_error":
    st.info(f"⚙️ **HỆ THỐNG PHÁT HIỆN SỰ CỐ:** {trend_msg}")
else:
    st.success(f"🟢 **XU HƯỚNG ỔN ĐỊNH:** {trend_msg}")

# --- PHÂN TÍCH GIẢI PHÁP NHANH & GỬI TELEGRAM ALERTS ---
quick_solution = get_quick_solution(latest_entry["VPD_raw"], vpd_min, vpd_max, now_rt.hour)
st.info(f"💡 **Khuyến nghị xử lý nhanh từ chuyên gia nông học:** {quick_solution}")

# Kích hoạt bắn tin nhắn khẩn cấp lên Group/Telegram cá nhân nếu cấu hình bật
if enable_tg and ("Lý tưởng" not in latest_entry["Trạng thái"]) and tg_token and tg_chat_id:
    alert_text = (
        f"🚨 **CẢNH BÁO VI KHÍ HẬU FARM ĐÀ LẠT** 🚨\n\n"
        f"🌿 Cây trồng: {cay_selected}\n"
        f"⏰ Thời gian: {latest_entry['Hiển thị Giờ']}\n"
        f"🌡️ Nhiệt độ: {latest_entry['Nhiệt độ (°C)']}°C | 💧 Độ ẩm: {latest_entry['Độ ẩm (%)']}%\n"
        f"📊 VPD đo được: *{latest_entry['VPD (kPa)']} kPa* (Ngưỡng an toàn: {vpd_min} - {vpd_max} kPa)\n"
        f"⚠️ Hiện trạng: *{latest_entry['Trạng thái']}*\n"
        f"🔮 Dự báo xu hướng: {trend_msg}\n\n"
        f"🛠️ **Giải pháp đề xuất:** {quick_solution}"
    )
    # Cơ chế kiểm tra chống spam gửi lặp tin nhắn liên tục trong cùng 1 phút
    if "last_tg_sent_time" not in st.session_state or (datetime.now() - st.session_state.last_tg_sent_time > timedelta(minutes=5)):
        sent_success = send_telegram_message(tg_token, tg_chat_id, alert_text)
        if sent_success:
            st.session_state.last_tg_sent_time = datetime.now()
            st.sidebar.success("✅ Đã gửi tin nhắn cảnh báo qua Telegram!")
        else:
            st.sidebar.error("❌ Gửi cảnh báo Telegram thất bại. Kiểm tra Token/ID!")

# --- KHU VỰC TRỰC QUAN HÓA BIỂU ĐỒ (CHARTS) ---
st.markdown("---")
st.subheader("📊 Đồ Thị Phân Tích Chu Kỳ Dữ Liệu Biến Thiên")

# Tách thành hai tab chức năng để giao diện gọn gàng sạch sẽ
tab_micro, tab_stress = st.tabs(["📈 Biến Thiên Vi Khí Hậu Hợp Nhất", "⏳ Lịch Sử Stress Của Cây Trồng"])

with tab_micro:
    st.markdown("##### 💡 Biểu đồ gộp Nhiệt độ & Độ ẩm (Nhìn chung thang đo trục đứng bên trái)")
    # GỌI HÀM BIỂU ĐỒ GỘP CHUNG 1 TRỤC BÊN TRÁI ĐÃ CẬP NHẬT
    st.altair_chart(draw_combined_temp_humidity_chart(df_display), use_container_width=True)
    
    st.markdown("##### 🎯 Biểu đồ áp suất hơi thâm hụt VPD đối chiếu dải nền lý tưởng")
    # Biểu đồ VPD giữ nguyên các dải màu phân vùng (Quá ẩm / Lý tưởng / Quá khô)
    st.altair_chart(draw_vpd_chart(df_display, vpd_min, vpd_max), use_container_width=True)

with tab_stress:
    st.markdown("##### 🛑 Thống kê thời gian tích lũy stress của cây trồng (Trong 24h qua)")
    stress_hours, stress_msg_hours = calculate_plant_stress_hours(st.session_state.simulation_data, vpd_min, vpd_max)
    
    s_col1, s_col2 = st.columns([1, 2])
    with s_col1:
        st.metric(label="Tổng số giờ cây bị stress nặng", value=f"{stress_hours} Giờ / 24h", delta=f"Ngưỡng biên: {vpd_min}-{vpd_max} kPa", delta_color="off")
    with s_col2:
        st.write("")
        st.write(stress_msg_hours)

# --- BÁO CÁO TỔNG HỢP THEO BUỔI CHU KỲ SINH HỌC ---
st.markdown("---")
st.markdown("##### 📊 BÁO CÁO PHÂN TÍCH TỔNG HỢP THEO CÁC BUỔI TRONG NGÀY")
df_f_blk = df_display.copy()

if len(df_f_blk) > 0:
    df_f_blk["Hour"] = df_f_blk["datetime_internal"].dt.hour
    
    # Ép khối buổi giống hàm phân tích của file analytics
    def b_assign(h):
        if 5 <= h < 10: return "🌅 Sáng (05h - 10h)"
        if 10 <= h < 15: return "☀️ Trưa (10h - 15h)"
        if 15 <= h < 19: return "🌇 Chiều (15h - 19h)"
        if 19 <= h < 23: return "🌌 Tối (19h - 23h)"
        return "🌙 Khuya (23h - 05h)"
        
    df_f_blk["Buổi"] = df_f_blk["Hour"].apply(b_assign)
    
    # Tính toán trung bình các chỉ số theo từng buổi
    b_sum = df_f_blk.groupby("Buổi").agg({
        "Nhiệt độ (°C)": "mean", 
        "Độ ẩm (%)": "mean", 
        "VPD_raw": "mean"
    }).reindex([
        "🌅 Sáng (05h - 10h)", 
        "☀️ Trưa (10h - 15h)", 
        "🌇 Chiều (15h - 19h)", 
        "🌌 Tối (19h - 23h)", 
        "🌙 Khuya (23h - 05h)"
    ]).dropna()
    
    # Đổi tên cột hiển thị và làm tròn
    b_sum["VPD (kPa)"] = b_sum["VPD_raw"].round(2)
    b_sum["Nhiệt độ (°C)"] = b_sum["Nhiệt độ (°C)"].round(1)
    b_sum["Độ ẩm (%)"] = b_sum["Độ ẩm (%)"].round(1)
    
    # Hiển thị bảng tổng hợp dữ liệu tĩnh ra ngoài Streamlit
    st.dataframe(b_sum[["Nhiệt độ (°C)", "Độ ẩm (%)", "VPD (kPa)"]], use_container_width=True)
else:
    st.info("Chưa có đủ chu kỳ dữ liệu để kết xuất bảng tổng hợp buổi.")
