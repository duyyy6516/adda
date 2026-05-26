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
        draw_vpd_chart,
        draw_combined_temp_humidity_chart
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

# --- XỬ LÝ NHẬP FILE CẤU HÌNH QUÁ KHỨ (LOG FILE) ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 📂 Khôi phục chu kỳ từ Tệp nhật ký")
uploaded_file = st.sidebar.file_uploader("Tải lên file dữ liệu JSON lịch sử:", type=["json"])

if uploaded_file is not None and not st.session_state.is_running:
    try:
        raw_data = json.load(uploaded_file)
        parsed_history = []
        for item in raw_data:
            # Chuyển đổi chuỗi ngược lại thành datetime nội bộ an toàn
            dt_obj = datetime.strptime(item["Thời điểm (Mô phỏng)"], "%d/%m/%Y %H:%M")
            parsed_history.append({
                "Thời điểm (Mô phỏng)": item["Thời điểm (Mô phỏng)"],
                "datetime_internal": dt_obj,
                "Nhiệt độ (°C)": float(item["Nhiệt độ (°C)"]),
                "Độ ẩm (%)": float(item["Độ ẩm (%)"]),
                "VPD (kPa)": float(item["VPD (kPa)"]),
                "VPD_raw": float(item.get("VPD_raw", item["VPD (kPa)"])),
                "Trạng thái": item["Trạng thái"],
                "Hiển thị Giờ": dt_obj.strftime("%H:%M")
            })
        # Sắp xếp lịch sử theo thời gian mới nhất lên đầu
        parsed_history.sort(key=lambda x: x["datetime_internal"], reverse=True)
        st.session_state.history = parsed_history
        if parsed_history:
            st.session_state.sim_time = parsed_history[0]["datetime_internal"]
        st.sidebar.success(f"✅ Đã đồng bộ thành công {len(parsed_history)} mốc chu kỳ lịch sử!")
    except Exception as e:
        st.sidebar.error(f"❌ Định dạng file lỗi hoặc không khớp cấu trúc chỉ số: {e}")

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

    # 3. ĐỒ THỊ TRỰC QUAN HÓA (Đã đổi từ 3 đồ thị rời sang 2 đồ thị: Gộp + VPD mục tiêu)
    st.markdown("---")
    st.markdown("### 📉 Đồ thị theo dõi Biến động Dữ liệu Lịch sử")
    
    # Chuẩn bị dữ liệu vẽ đồ thị (đảo ngược lại để hiển thị mốc thời gian xuôi dòng từ trái qua phải)
    df_chart_source = pd.DataFrame(st.session_state.history).iloc[::-1].reset_index(drop=True)
    
    col_g1, col_g2 = st.columns([1, 1])
    with col_g1:
        st.markdown("<p style='text-align: center; font-weight: bold; color: #2E7D32;'>Biểu đồ Nhiệt độ & Độ ẩm lồng nhau</p>", unsafe_allow_html=True)
        st.altair_chart(draw_combined_temp_humidity_chart(df_chart_source), use_container_width=True)
    with col_g2:
        st.markdown("<p style='text-align: center; font-weight: bold; color: #2E7D32;'>Biểu đồ Dải An Toàn VPD Mục Tiêu</p>", unsafe_allow_html=True)
        st.altair_chart(draw_vpd_chart(df_chart_source, vpd_min, vpd_max), use_container_width=True)

    # 4. KHỐI HIỂN THỊ BẢNG BIỂU TUẦN TỰ XẾP BÊN DƯỚI ĐỒ THỊ
    # Chuẩn bị dữ liệu xử lý chu kỳ cho thuật toán
    df_f_blk = pd.DataFrame(st.session_state.history)

    # --- BÁO CÁO THEO BUỔI ---
    st.markdown("---")
    st.markdown("##### 📊 BÁO CÁO PHÂN TÍCH TỔNG HỢP THEO BUỔI CHU KỲ (Dữ liệu gốc)")
    
    # Gọi hàm xử lý phân đoạn từ module analytics của bạn để tính toán chính xác
    blk_report = analyze_day_by_blocks_rt(df_f_blk, vpd_min, vpd_max)
    if blk_report:
        st.dataframe(pd.DataFrame(blk_report), use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có đủ dữ liệu phân đoạn theo mốc giờ chu kỳ để lập báo cáo tổng hợp.")

    # --- NHẬT KÝ SỐ LIỆU LỊCH SỬ CHI TIẾT ---
    st.markdown("---")
    st.markdown("##### 📝 NHẬT KÝ SỐ LIỆU LỊCH SỬ CHI TIẾT (Bảng dữ liệu thô)")
    
    df_display = pd.DataFrame(st.session_state.history)
    if not df_display.empty:
        df_display_clean = df_display[["Thời điểm (Mô phỏng)", "Nhiệt độ (°C)", "Độ ẩm (%)", "VPD (kPa)", "Trạng thái"]]
        st.dataframe(df_display_clean, use_container_width=True, hide_index=True)
        
        # --- KHỐI TẢI XUẤT FILE NÂNG CAO ---
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            # Tạo file sao lưu cấu hình dạng JSON
            clean_json_list = []
            for _, r in df_display.iterrows():
                clean_json_list.append({
                    "Thời điểm (Mô phỏng)": r["Thời điểm (Mô phỏng)"],
                    "Nhiệt độ (°C)": float(r["Nhiệt độ (°C)"]),
                    "Độ ẩm (%)": float(r["Độ ẩm (%)"]),
                    "VPD (kPa)": float(r["VPD (kPa)"]),
                    "VPD_raw": float(r["VPD_raw"]),
                    "Trạng thái": r["Trạng thái"]
                })
            json_str = json.dumps(clean_json_list, indent=4, ensure_ascii=False)
            st.download_button(
                label="📥 Tải tệp sao lưu dữ liệu (.JSON)",
                data=json_str,
                file_name=f"vpd_history_backup_{datetime.now().strftime('%d%m%Y_%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )
        with col_down2:
            try:
                import io
                output_buffer = io.BytesIO()
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    df_display_clean.to_excel(writer, index=False, sheet_name='VPD_Report_Data')
                excel_data = output_buffer.getvalue()
                st.download_button(
                    label="📥 Xuất bảng báo cáo số liệu (.XLSX)",
                    data=excel_data,
                    file_name=f"vpd_farm_report_{datetime.now().strftime('%d%m%Y_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Không thể tạo file excel kết xuất: {e}")
    else:
        st.info("Nhật ký trống. Vui lòng bấm cập nhật dữ liệu mô phỏng để ghi nhận nhật ký.")

else:
    st.info("👋 Chào mừng bạn đến với hệ thống quản lý VPD. Hãy bấm nút **'Chạy / Cập nhật mốc tiếp theo'** ở phía trên để bắt đầu mô phỏng và phân tích dữ liệu!")
