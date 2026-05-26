import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import sys
import os

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
        draw_vpd_chart,
        draw_temp_humidity_combo_chart
    )
except ModuleNotFoundError as e:
    st.error(f"❌ Không tìm thấy module bổ trợ: {e.name}")
    st.stop()

st.set_page_config(page_title="VPD Farm Analytics", page_icon="🌿", layout="wide")

# CẤU TRÚC NGƯỠNG VPD CỐ ĐỊNH PHẲNG (ĐÃ XÓA KHUNG GIỜ)
DANH_SACH_CAY = {
    "🍓 Dâu tây Đà Lạt (Hoa / Trái)": (0.6, 1.2),
    "🍓 Dâu tây Đà Lạt (Giai đoạn ngó/cây con)": (0.4, 0.8),
    "🌹 Hoa hồng (Nhà màng)": (0.7, 1.4),
    "🍅 Cà chua Beef thủy canh": (0.8, 1.5),
    "🥬 Xà lách thủy canh hồi lưu": (0.5, 1.0)
}

def get_current_vpd_range(cay_chon):
    """Lấy trực tiếp ngưỡng VPD phẳng của cây được chọn, không phụ thuộc thời gian"""
    return DANH_SACH_CAY.get(cay_chon, (0.4, 1.2))

# --- GIAO DIỆN CHÍNH ---
st.title("🌿 Hệ Thống Giám Sát & Dự Báo Chỉ Số VPD Nông Nghiệp")
st.markdown("---")

# Khởi tạo trạng thái phiên lưu trữ (Session State)
if "history_rt" not in st.session_state:
    st.session_state.history_rt = []
if "sim_time" not in st.session_state:
    st.session_state.sim_time = datetime.now()
if "alert_logs" not in st.session_state:
    st.session_state.alert_logs = []

# THANH SIDEBAR: CẤU HÌNH VÀ THÔNG TIN CÂY TRỒNG
with st.sidebar:
    st.header("⚙️ Cấu Hình Hệ Thống")
    
    f_opt = st.selectbox("Chọn mô hình cây trồng:", list(DANH_SACH_CAY.keys()))
    v_min, v_max = get_current_vpd_range(f_opt)
    
    st.info(f"**Ngưỡng VPD mục tiêu cho cả ngày:**\n* Tối thiểu: `{v_min} kPa`\n* Tối đa: `{v_max} kPa`")
    
    st.markdown("---")
    st.subheader("🤖 Cấu Hình Cảnh Báo Telegram")
    bot_token = st.text_input("Bot Token:", value="", type="password", placeholder="Điền Token...")
    chat_id = st.text_input("Chat ID:", value="", placeholder="Điền Chat ID...")
    
    st.markdown("---")
    if st.button("🔄 Xóa Lịch Sử Realtime", use_container_width=True):
        st.session_state.history_rt = []
        st.session_state.alert_logs = []
        st.success("Đã xóa toàn bộ lịch sử chạy realtime!")

# GIAO DIỆN CHIA TÁP CHỨC NĂNG
tab1, tab2 = st.tabs(["⚡ Giám Sát Thời Gian Thực (Realtime)", "📂 Phân Tích File Lịch Sử (Log File)"])

# ----------------- TAB 1: REALTIME MONITORING -----------------
with tab1:
    st.subheader("📡 Giám Sát Biến Động Vi Khí Hậu Thực Tế")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"⏱️ **Mốc thời gian mô phỏng:** {st.session_state.sim_time.strftime('%H:%M:%S (%d/%m/%Y)')}")
    
    # Giả lập luồng nhận dữ liệu
    t_sim, h_sim = get_weather_by_time(st.session_state.sim_time)
    vpd_sim = calculate_vpd(t_sim, h_sim)
    
    # Lưu vào bộ nhớ đệm lịch sử
    current_log = {
        "Hiển thị Giờ": st.session_state.sim_time.strftime("%H:%M"),
        "Hour": st.session_state.sim_time.hour,
        "Nhiệt độ (°C)": t_sim,
        "Độ ẩm (%)": h_sim,
        "VPD (kPa)": round(vpd_sim, 2)
    }
    
    # Thêm mới lên đầu danh sách để thuật toán xu hướng đọc (đọc các phần tử gần nhất)
    st.session_state.history_rt.insert(0, current_log)
    if len(st.session_state.history_rt) > 24:
        st.session_state.history_rt.pop()
        
    df_rt = pd.DataFrame(st.session_state.history_rt[::-1]) # Đảo chuỗi để vẽ biểu đồ theo trục thời gian xuôi
    
    # Phân loại trạng thái hiện tại dựa trên ngưỡng phẳng
    if vpd_sim < v_min:
        status_text, status_color = "🟦 QUÁ ẨM", "blue"
    elif vpd_sim <= v_max:
        status_text, status_color = "🟩 LÝ TƯỞNG", "green"
    else:
        status_text, status_color = "🟥 QUÁ KHÔ", "red"
        
    # Hiện thị Khung số liệu (Metrics)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Nhiệt độ phòng màng", f"{t_sim} °C")
    m2.metric("Độ ẩm không khí", f"{h_sim} %")
    m3.metric("Áp suất thâm hụt (VPD)", f"{round(vpd_sim, 2)} kPa")
    m4.markdown(f"<div style='padding:10px; background-color:rgba(0,0,0,0.05); border-radius:5px; text-align:center;'>Trạng thái:<br><b style='color:{status_color}; font-size:20px;'>{status_text}</b></div>", unsafe_allow_html=True)
    
    # 🤖 Thuật toán dự báo xu hướng & Gợi ý hành động giải pháp nhanh
    st.markdown("### 🔍 Phân Tích Thông Minh & Gợi Ý Hành Động")
    trend_msg, trend_status = predict_vpd_trend_v3(st.session_state.history_rt, st.session_state.sim_time.hour, v_min, v_max)
    
    if trend_status == "danger":
        st.error(trend_msg)
        # Gửi cảnh báo Telegram nếu bật cấu hình cấu hình đầy đủ
        if bot_token and chat_id:
            alert_msg = f"⚠️ [VPD WARNING] - {f_opt}\n- VPD hiện tại: {round(vpd_sim, 2)} kPa ({status_text})\n- Xu hướng: {trend_msg}\n- Khuyến nghị: Cần kiểm tra hệ thống điều hòa vi khí hậu vườn ngay!"
            if send_telegram_message(bot_token, chat_id, alert_msg):
                st.session_state.alert_logs.append(f"⏱️ {st.session_state.sim_time.strftime('%H:%M')} -> Đã gửi cảnh báo Telegram thành công.")
    elif trend_status == "warning":
        st.warning(trend_msg)
    else:
        st.success(trend_msg)
        
    # Lấy giải pháp hành động nhanh tương ứng theo mốc giờ thực tế
    action_solution = get_quick_solution(vpd_sim, v_min, v_max, st.session_state.sim_time.hour)
    st.info(f"💡 **Khuyến nghị kỹ thuật xử lý nhanh:** {action_solution}")
    
    # Đồ thị trực quan
    st.markdown("### 📊 Biểu đồ Giám Sát Vi Khí Hậu Tích Hợp")
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("<center><b>Biến động chỉ số VPD thực tế đối chiếu với vùng lý tưởng (Vùng xanh)</b></center>", unsafe_allow_html=True)
        st.altair_chart(draw_vpd_chart(df_rt, v_min, v_max), use_container_width=True)
    with g2:
        st.markdown("<center><b>Biến động tương quan kép Nhiệt độ (°C) và Độ ẩm (%)</b></center>", unsafe_allow_html=True)
        st.altair_chart(draw_temp_humidity_combo_chart(df_rt), use_container_width=True)
        
    # Danh sách nhật ký cảnh báo Telegram
    if st.session_state.alert_logs:
        with st.expander("💬 Lịch sử gửi tin nhắn Telegram"):
            for log in st.session_state.alert_logs[::-1]:
                st.caption(log)
                
    # Nút bấm chuyển tiếp bước thời gian để chạy thử nghiệm nghiệm thu
    if st.button("⏭️ Giả lập mốc thời gian tiếp theo (+60 Phút)"):
        st.session_state.sim_time += timedelta(hours=1)
        st.rerun()

# ----------------- TAB 2: LOG FILE ANALYTICS -----------------
with tab2:
    st.subheader("📂 Phân Tích Báo Cáo Từ File Dữ Liệu Lịch Sử")
    st.markdown("Tải lên file excel hoặc csv chứa dữ liệu của trạm cảm biến thu thập để hệ thống chạy phân tích tổng quát.")
    
    uploaded_file = st.file_uploader("Chọn file lịch sử (Hỗ trợ định dạng .csv, .xlsx):", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_file = pd.read_csv(uploaded_file)
            else:
                df_file = pd.read_excel(uploaded_file)
                
            # Chuẩn hóa kiểm tra cột dữ liệu đầu vào cần thiết
            req_cols = ["Nhiệt độ (°C)", "Độ ẩm (%)"]
            if not all(col in df_file.columns for col in req_cols):
                st.error("❌ File tải lên sai định dạng! Yêu cầu bắt buộc phải có đầy đủ 2 cột: 'Nhiệt độ (°C)' và 'Độ ẩm (%)'")
            else:
                # Tự động tính toán lại cột VPD dựa trên dữ liệu gốc của file để đồng bộ
                df_file["VPD_raw"] = df_file.apply(lambda r: calculate_vpd(r["Nhiệt độ (°C)"], r["Độ ẩm (%)"]), axis=1)
                df_file["VPD (kPa)"] = df_file["VPD_raw"].round(2)
                
                if "Hour" not in df_file.columns:
                    df_file["Hour"] = 12 # Mặc định nếu file ko có mốc giờ cụ thể
                if "Hiển thị Giờ" not in df_file.columns:
                    df_file["Hiển thị Giờ"] = df_file.index.astype(str)
                    
                st.success(f" Đọc dữ liệu thành công! Tổng số bản ghi nhận: {len(df_file)} dòng.")
                
                # Biểu diễn biểu đồ phân tích dữ liệu lịch sử file
                st.markdown("### 📊 Phân Tích Đồ Thị File")
                fg1, fg2 = st.columns(2)
                with fg1:
                    st.altair_chart(draw_vpd_chart(df_file, v_min, v_max), use_container_width=True)
                with fg2:
                    st.altair_chart(draw_temp_humidity_combo_chart(df_file), use_container_width=True)
                
                # Thống kê tổng hợp số giờ căng thẳng của cây trồng (Plant Stress Hours)
                st.markdown("### 🧮 Thống Kê Tổng Hợp Mức Độ Căng Thẳng (Plant Stress)")
                stress_res = calculate_plant_stress_hours(df_file, v_min, v_max)
                
                sm1, sm2, sm3 = st.columns(3)
                sm1.metric("Tổng thời gian lý tưởng", f"🟩 {stress_res['ideal_hours']} Giờ", f"{stress_res['ideal_pct']}%")
                sm2.metric("Tổng thời gian quá ẩm (Stress)", f"🟦 {stress_res['low_hours']} Giờ", f"{stress_res['low_pct']}%", delta_color="inverse")
                sm3.metric("Tổng thời gian quá khô (Stress)", f"🟥 {stress_res['high_hours']} Giờ", f"{stress_res['high_pct']}%", delta_color="inverse")
                
                # Phân tích chi tiết số liệu gom cụm theo các khoảng thời gian
                st.markdown("### 🗓️ Bảng Gom Cụm Đánh Giá Sơ Bộ")
                
                def b_assign(h):
                    if 5 <= h < 11: return "🌅 Sáng"
                    elif 11 <= h < 15: return "☀️ Trưa"
                    elif 15 <= h < 19: return "🌇 Chiều"
                    else: return "🌙 Đêm/Khuya"
                    
                df_file["Buổi"] = df_file["Hour"].apply(b_assign)
                b_sum = df_file.groupby("Buổi").agg({"Nhiệt độ (°C)": "mean", "Độ ẩm (%)": "mean", "VPD_raw": "mean"}).reindex(["🌅 Sáng", "☀️ Trưa", "🌇 Chiều", "🌙 Đêm/Khuya"]).dropna(how="all").reset_index()
                b_sum.columns = ["Khoảng thời gian", "Nhiệt độ TB (°C)", "Độ ẩm TB (%)", "VPD TB (kPa)"]
                for c in ["Nhiệt độ TB (°C)", "Độ ẩm TB (%)", "VPD TB (kPa)"]: 
                    b_sum[c] = b_sum[c].round(2)
                
                def evaluate_block_row_flat(row):
                    vpd = row["VPD TB (kPa)"]
                    if vpd < v_min: return "🟦 Quá ẩm"
                    elif vpd <= v_max: return "🟩 Lý tưởng"
                    return "🟥 Quá khô"
                    
                b_sum["Đánh giá trạng thái"] = b_sum.apply(evaluate_block_row_flat, axis=1)
                st.dataframe(b_sum, use_container_width=True, hide_index=True)
                
        except Exception as e:
            st.error(f"❌ Xảy ra sự cố khi xử lý dữ liệu file: {str(e)}")
