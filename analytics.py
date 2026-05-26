import pandas as pd
import numpy as np

def predict_vpd_trend_v3(history_data, current_hour, vpd_min, vpd_max):
    if not history_data or len(history_data) < 3:
        return "📊 Hệ thống đang tích lũy thêm chu kỳ dữ liệu để phân tích xu hướng...", "normal"
    
    try:
        v1 = float(history_data[0]["VPD (kPa)"])
        v2 = float(history_data[1]["VPD (kPa)"])
        v3 = float(history_data[2]["VPD (kPa)"])
        
        diff_1 = v1 - v2
        diff_2 = v2 - v3
        
        if abs(diff_1) < 0.005 and abs(diff_2) < 0.005:
            if v1 < vpd_min:
                return "🟦 CẢNH BÁO: Hiện trạng quá ẩm đang bị kẹt đứng im lâu. Cần bật quạt đối lưu lập tức.", "danger_blue"
            elif v1 > vpd_max:
                return "🟥 CẢNH BÁO: Hiện trạng quá khô đang bị kẹt đứng im lâu. Cần bật phun sương lập tức.", "danger_red"
            return "🟩 Hệ thống ổn định đứng im ở ngưỡng lý tưởng.", "normal"
            
        if diff_1 > 0.02 and diff_2 > 0.02:
            if v1 > vpd_max - 0.15:
                return "🔺 XU HƯỚNG: VPD ĐANG LAO DỐC TĂNG NHANH KHÔ NÓNG. Chuẩn bị bật phun sương giảm nhiệt!", "danger_red"
            return "📈 Xu hướng: VPD đang tăng dần.", "normal"
            
        if diff_1 < -0.02 and diff_2 < -0.02:
            if v1 < vpd_min + 0.15:
                return "🔻 XU HƯỚNG: VPD ĐANG TỤT DỐC GIẢM NHANH QUÁ ẨM. Chuẩn bị bật quạt đối lưu xả ẩm!", "danger_blue"
            return "📉 Xu hướng: VPD đang giảm dần.", "normal"
            
        return "🔄 Xu hướng: VPD dao động ổn định trong biên độ an toàn.", "normal"
    except Exception:
        return "📊 Đang tính toán dữ liệu xu hướng...", "normal"

def calculate_plant_stress_hours(df, vpd_min, vpd_max, filter_type):
    try:
        dry_pts = len(df[df["Trạng thái"].str.contains("khô", case=False, na=False)])
        wet_pts = len(df[df["Trạng thái"].str.contains("ẩm", case=False, na=False)])
        
        if any(k in filter_type for k in ["1 Tuần gần nhất", "1 Tháng gần nhất", "Gom ngày"]):
            return {"dry_hours": round(dry_pts * 24.0, 1), "wet_hours": round(wet_pts * 24.0, 1)}
        elif "Xem toàn bộ dữ liệu gốc" in filter_type and len(df) > 50:
            return {"dry_hours": round(dry_pts * 1.0, 1), "wet_hours": round(wet_pts * 1.0, 1)}
        else:
            return {"dry_hours": round((dry_pts * 10) / 60, 1), "wet_hours": round((wet_pts * 10) / 60, 1)}
    except Exception:
        return {"dry_hours": 0.0, "wet_hours": 0.0}

def analyze_day_by_blocks_rt(history_list, h_sang, h_trua, h_chieu, h_dem, current_day=None):
    if not history_list:
        return pd.DataFrame()
        
    df = pd.DataFrame(history_list)
    if current_day:
        df = df[df["Ngày"] == current_day]
        
    if df.empty:
        return pd.DataFrame()
        
    df["Hour"] = df["datetime_internal"].dt.hour
    
    def assign_custom_block(h):
        if h_sang <= h < h_trua: return f"🌅 Sáng ({h_sang:02d}h-{h_trua:02d}h)"
        elif h_trua <= h < h_chieu: return f"☀️ Trưa ({h_trua:02d}h-{h_chieu:02d}h)"
        elif h_chieu <= h < h_dem: return f"🌇 Chiều ({h_chieu:02d}h-{h_dem:02d}h)"
        else: return f"🌙 Đêm/Khuya ({h_dem:02d}h-{h_sang:02d}h)"
        
    df["Buổi"] = df["Hour"].apply(assign_custom_block)
    
    order_list = [
        f"🌅 Sáng ({h_sang:02d}h-{h_trua:02d}h)",
        f"☀️ Trưa ({h_trua:02d}h-{h_chieu:02d}h)",
        f"🌇 Chiều ({h_chieu:02d}h-{h_dem:02d}h)",
        f"🌙 Đêm/Khuya ({h_dem:02d}h-{h_sang:02d}h)"
    ]
    
    summary = df.groupby("Buổi").agg({
        "Nhiệt độ (°C)": "mean",
        "Độ ẩm (%)": "mean",
        "VPD (kPa)": "mean"
    }).reindex(order_list).dropna().reset_index()
    
    if summary.empty:
        return pd.DataFrame(columns=["Khoảng thời gian", "Nhiệt độ TB", "Độ ẩm TB", "VPD TB", "Đánh giá sinh lý"])
        
    summary.columns = ["Khoảng thời gian", "Nhiệt độ TB (°C)", "Độ ẩm TB (%)", "VPD TB (kPa)"]
    for c in ["Nhiệt độ TB (°C)", "Độ ẩm TB (%)", "VPD TB (kPa)"]:
        summary[c] = summary[c].round(2)
        
    return summary
