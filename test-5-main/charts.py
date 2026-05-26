import altair as alt
import pandas as pd

def draw_vpd_chart(df, vpd_min, vpd_max):
    """
    Biểu đồ chỉ số VPD đối chiếu dải nền lý tưởng (Giữ nguyên gốc)
    """
    if df.empty:
        return alt.Chart(pd.DataFrame()).mark_blank()
    
    # 1. Đồng bộ cấu trúc dữ liệu dải biên tĩnh làm mỏ neo cho tham số Y2 của dải nền
    df_chart = df.copy()
    df_chart['y_min_bound'] = vpd_min
    df_chart['y_max_bound'] = vpd_max
    df_chart['y_floor'] = 0.0
    df_chart['y_roof'] = 3.0

    # 2. Định nghĩa trục X dùng chung ép kiểu Ordinal (:O) chống lặp mốc thời gian
    x_axis = alt.X(field='Hiển thị Giờ', type='ordinal', title='Mốc thời gian chu kỳ', sort=None)

    # 3. Xây dựng 3 lớp dải màu nền động bám biên dữ liệu gốc
    bg_under = alt.Chart(df_chart).mark_area(color='#E3F2FD', opacity=0.8).encode(
        x=x_axis,
        y=alt.Y(field='y_floor', type='quantitative'),
        y2=alt.Y2(field='y_min_bound')
    )
    
    bg_ideal = alt.Chart(df_chart).mark_area(color='#E8F5E9', opacity=0.8).encode(
        x=x_axis,
        y=alt.Y(field='y_min_bound', type='quantitative'),
        y2=alt.Y2(field='y_max_bound')
    )
    
    bg_over = alt.Chart(df_chart).mark_area(color='#FFEBEE', opacity=0.8).encode(
        x=x_axis,
        y=alt.Y(field='y_max_bound', type='quantitative'),
        y2=alt.Y2(field='y_roof')
    )

    # 4. Đường line dữ liệu VPD thực tế
    line = alt.Chart(df_chart).mark_line(color='#4A148C', strokeWidth=3).encode(
        x=x_axis,
        y=alt.Y(field='VPD (kPa)', type='quantitative', title='Áp suất thâm hụt VPD (kPa)', scale=alt.Scale(domain=[0.0, 3.0]))
    )
    
    points = alt.Chart(df_chart).mark_circle(color='#4A148C', size=60).encode(
        x=x_axis,
        y=alt.Y(field='VPD (kPa)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )

    return alt.layer(bg_under, bg_ideal, bg_over, line, points).properties(height=200).interactive().configure_axis(labelAngle=0)


def draw_combined_temp_humidity_chart(df):
    """
    Vẽ biểu đồ Nhiệt độ và Độ ẩm gộp chung, cùng bám sát vào 
    MỘT TRỤC TUNG DUY NHẤT Ở BÊN TRÁI.
    """
    if df.empty: 
        return alt.Chart(pd.DataFrame()).mark_blank()
    
    # Định nghĩa cấu hình trục X và trục Y chung nằm ở BÊN TRÁI
    x_axis = alt.X(field='Hiển thị Giờ', type='ordinal', title='Mốc thời gian', sort=None)
    shared_y_axis = alt.Y(
        title='Thang đo giá trị (Nhiệt độ °C / Độ ẩm %)', 
        type='quantitative',
        axis=alt.Axis(orient='left') # Ép xuất phát và hiển thị hoàn toàn bên trái
    )
    
    # 1. Đường biểu diễn Nhiệt độ (Màu đỏ)
    temp_line = alt.Chart(df).mark_line(color='#FF4B4B', strokeWidth=2.5).encode(
        x=x_axis,
        y=shared_y_axis.defaults(field='Nhiệt độ (°C)')
    )
    temp_points = alt.Chart(df).mark_circle(color='#B71C1C', size=50).encode(
        x=x_axis,
        y=shared_y_axis.defaults(field='Nhiệt độ (°C)'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )
    
    # 2. Đường biểu diễn Độ ẩm (Màu xanh dương)
    humidity_line = alt.Chart(df).mark_line(color='#0068C9', strokeWidth=2.5).encode(
        x=x_axis,
        y=shared_y_axis.defaults(field='Độ ẩm (%)')
    )
    humidity_points = alt.Chart(df).mark_square(color='#0D47A1', size=50).encode(
        x=x_axis,
        y=shared_y_axis.defaults(field='Độ ẩm (%)'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )
    
    # 3. Trộn các lớp lại thành một đồ thị thống nhất (Không dùng độc lập scale trục Y)
    combined_chart = alt.layer(
        temp_line, temp_points, 
        humidity_line, humidity_points
    ).properties(
        height=220,
        title="📈 Biến thiên tổng thể vi khí hậu: Nhiệt độ (°C) & Độ ẩm (%) bám chung trục trái"
    ).configure_axis(
        labelAngle=0
    ).interactive()
    
    return combined_chart
