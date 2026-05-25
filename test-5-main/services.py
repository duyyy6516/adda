def get_quick_solution(vpd: float, vpd_min: float, vpd_max: float, hour: int, temp: float = 25.0, rh: float = 70.0) -> str:
    """
    Trả về nguyên nhân cụ thể và giải pháp xử lý vi khí hậu chuyên sâu
    dựa trên tổ hợp các thông số VPD, Nhiệt độ (Temp) và Độ ẩm (RH).
    """
    # TRƯỜNG HỢP 1: LÝ TƯỞNG
    if vpd_min <= vpd <= vpd_max:
        return "Môi trường hoàn hảo. Duy trì trạng thái hiện tại của nhà kính."

    # TRƯỜNG HỢP 2: LÀM KHÔ / QUÁ KHÔ (VPD CAO)
    elif vpd > vpd_max:
        if temp > 28.0:
            return "Do KHÔNG KHÍ QUÁ NÓNG (T tăng cao vọt). Giải pháp: Kéo lưới cắt nắng (giảm 50-70% bức xạ), bật phun sương mịn áp suất cao hoặc hệ thống Cooling Pad, mở tối đa bạt mái/bạt hông để thông gió hạ nhiệt."
        else:
            return "Do GIÓ HOẶC KHÔNG KHÍ HANH KHÔ (RH tụt sâu). Giải pháp: Bật phun sương bù ẩm theo chu kỳ ngắn (Phun 30s, nghỉ 3p), khép bớt bạt hông hướng đón gió chính để giữ ẩm, tăng nhẹ lưu lượng tưới nhỏ giọt."

    # TRƯỜNG HỢP 3: QUÁ ẨM (VPD THẤP)
    else:
        if temp < 18.0:
            return "Do LẠNH TÍCH TỤ ẨM (Nhiệt độ sụt giảm mạnh). Giải pháp: Đóng kín bạt mái và bạt hông giữ nhiệt ban đêm, bật quạt đối lưu tầm cao để xua sương muối/khí lạnh, kích hoạt đèn sưởi/lò đốt nâng nhiệt nhẹ."
        else:
            return "Do KHÔNG KHÍ BỊ KẸT ẨM (Đứng gió, thoát hơi lá tụ tụ). Giải pháp: Ngắt ngay phun sương, mở bạt mái thông gió (Top-vent) xả ẩm, bật quạt thông gió hướng ra ngoài và quạt đối lưu làm khô bề mặt lá."
