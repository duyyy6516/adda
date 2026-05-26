import pandas as pd
import numpy as np

def predict_vpd_trend_v3(history_data, current_hour, vpd_min, vpd_max):
    """
    Thuật toán dự báo xu hướng nâng cao:
    - Dự báo thuần túy dựa trên biến động toán học (Độ dốc/Slope) của 3 mốc gần nhất.
    - Đối chiếu trực tiếp với ngưỡng phẳng của cây trồng để đưa ra cảnh báo sớm.
    """
    if not history_data or len(history_data) < 3:
        return "📊 Hệ thống đang tích lũy thêm chu kỳ dữ liệu để phân tích xu hướng...", "normal"
    
    try:
        # Lấy thông số VPD của 3 điểm gần nhất (điểm 0 là mới nhất)
        v1 = float(history_data[0]["VPD (kPa)"])
        v2 = float(history_data[1]["VPD (kPa)"])
        v3 = float(history_data[2]["VPD (kPa)"])
        
        diff_1 = v1 - v2
        diff_2 = v2 - v3
        
        # Trường hợp 1: Dữ liệu đứng im hoàn toàn (Cảm biến bị lỗi hoặc kẹt)
        if abs(diff_1) < 0.005 and abs(diff_2) < 0.005:
            if v1 < vpd_min:
                return "🟦 CẢNH BÁO: Hiện trạng quá ẩm đang bị kẹt đứng im lâu. Cần bật quạt đối lưu lập tức!", "danger"
            elif v1 > vpd_max:
                return "🟥 CẢNH BÁO: Hiện trạng quá khô bị kẹt đứng im. Cần kích hoạt bù ẩm ngay!", "danger"
            return "🟩 Hệ thống đang duy trì trạng thái ổn định lý tưởng hoàn hảo.", "normal"
            
        # Tính toán độ dốc (Slope) dựa trên xu hướng
        slope = (diff_1 + diff_2) / 2.0
        
        # Trường hợp 2: VPD hiện tại đã vượt ngưỡng nguy hiểm
        if v1 < vpd_min:
            if slope < 0:
                return f"🚨 NGUY HIỂM: Khí hậu đang QUÁ ẨM ({v1} kPa) và có xu hướng giảm sâu thêm (Độ dốc: {round(slope,3)}). Kích hoạt xả ẩm khẩn cấp!", "danger"
            else:
                return f"⚠️ CẢNH BÁO: Khí hậu đang ẩm thấp thấp dưới ngưỡng ({v1} kPa) nhưng đang có dấu hiệu tự phục hồi đi lên lại.", "warning"
                
        if v1 > vpd_max:
            if slope > 0:
                return f"🚨 NGUY HIỂM: Khí hậu đang QUÁ KHÔ ({v1} kPa) và có xu hướng tiếp tục tăng gắt (Độ dốc: +{round(slope,3)}). Kích hoạt phun sương khẩn cấp!", "danger"
            else:
                return f"⚠️ CẢNH BÁO: Khí hậu đang khô nóng vượt ngưỡng ({v1} kPa) nhưng đang có xu hướng hạ nhiệt đi xuống.", "warning"
                
        # Trường hợp 3: Hiện tại VPD đang an toàn nhưng xu hướng lao dốc/phi mã sắp vượt ngưỡng
        predicted_next = v1 + slope
        if predicted_next < vpd_min:
            return f"⚠️ CẢNH BÁO SỚM: Chỉ số VPD an toàn ({v1} kPa) nhưng đang giảm nhanh đâm thẳng về vùng quá ẩm ở chu kỳ tới.", "warning"
        if predicted_next > vpd_max:
            return f"⚠️ CẢNH BÁO SỚM: Chỉ số VPD an toàn ({v1} kPa) nhưng đang tăng mạnh có nguy cơ gây sốc khô ở chu kỳ tới.", "warning"
            
        return "🟩 Chỉ số vi khí hậu VPD đang nằm trong dải phân phối lý tưởng, an toàn cho cây.", "normal"
        
    except Exception as e:
        return f"⚠️ Lỗi xử lý thuật toán xu hướng: {str(e)}", "normal"

def calculate_plant_stress_hours(df, vpd_min, vpd_max):
    """Tính toán chi tiết tổng số bản ghi/số giờ bị stress vi khí hậu dựa theo ngưỡng phẳng"""
    total = len(df)
    if total == 0:
        return {"ideal_hours": 0, "low_hours": 0, "high_hours": 0, "ideal_pct": 0, "low_pct": 0, "high_pct": 0}
        
    low_count = int((df["VPD (kPa)"] < vpd_min).sum())
    high_count = int((df["VPD (kPa)"] > vpd_max).sum())
    ideal_count = total - (low_count + high_count)
    
    return {
        "ideal_hours": ideal_count,
        "low_hours": low_count,
        "high_hours": high_count,
        "ideal_pct": round((ideal_count / total) * 100, 1),
        "low_pct": round((low_count / total) * 100, 1),
        "high_pct": round((high_count / total) * 100, 1)
    }

def analyze_day_by_blocks_rt(df_filtered, vpd_min, vpd_max):
    """Hàm phân tích tổng hợp báo cáo bằng chuỗi chu kỳ"""
    if df_filtered.empty:
        return []
        
    def assign_block(h):
        if 5 <= h < 11: return "🌅 Sáng (05h - 11h)"
        elif 11 <= h < 15: return "☀️ Trưa (11h - 15h)"
        elif 15 <= h < 19: return "🌇 Chiều (15h - 19h)"
        else: return "🌙 Đêm/Khuya (19h - 05h)"
        
    df_filtered["Buổi"] = df_filtered["Hour"].apply(assign_block)
    
    summary = df_filtered.groupby("Buổi").agg({
        "Nhiệt độ (°C)": "mean", "Độ ẩm (%)": "mean", "VPD (kPa)": "mean"
    }).reindex(["🌅 Sáng (05h - 11h)", "☀️ Trưa (11h - 15h)", "🌇 Chiều (15h - 19h)", "🌙 Đêm/Khuya (19h - 05h)"]).dropna()
    
    report_data = []
    for idx, row in summary.iterrows():
        avg_v = round(row["VPD (kPa)"], 2)
        if avg_v < vpd_min:
            status = "⚠️ Quá ẩm"
        elif avg_v <= vpd_max:
            status = "✅ Lý tưởng"
        else:
            status = "⚠️ Quá khô"
            
        report_data.append({
            "Khung giờ": idx,
            "Nhiệt độ TB": round(row["Nhiệt độ (°C)"], 1),
            "Độ ẩm TB": round(row["Độ ẩm (%)"], 1),
            "VPD trung bình": avg_v,
            "Đánh giá": status
        })
    return report_data
