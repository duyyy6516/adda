import altair as alt
import pandas as pd

def draw_vpd_chart(df, vpd_min, vpd_max):
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
        y=alt.Y(field='y_min_bound', type='quantitative', title='Áp suất hơi thâm hụt VPD (kPa)'),
        y2=alt.Y2(field='y_max_bound')
    )
    
    bg_over = alt.Chart(df_chart).mark_area(color='#FFF3E0', opacity=0.8).encode(
        x=x_axis,
        y=alt.Y(field='y_max_bound', type='quantitative'),
        y2=alt.Y2(field='y_roof')
    )

    # 4. Vẽ đường giá trị VPD thực tế chạy đè lên dải nền
    line_actual = alt.Chart(df_chart).mark_line(color='#2E7D32', strokeWidth=3, point=alt.OverlayMarkDef(color='#1B5E20', size=60)).encode(
        x=x_axis,
        y=alt.Y(field='VPD (kPa)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )

    # 5. Lồng ghép các tầng bản đồ trực quan bằng toán tử Layer của Altair
    final_chart = alt.layer(bg_under, bg_ideal, bg_over, line_actual).properties(
        height=200
    ).interactive()

    return final_chart.configure_axis(labelAngle=0)


def draw_temperature_chart(df):
    if df.empty: 
        return alt.Chart(pd.DataFrame()).mark_blank()
    
    x_axis = alt.X(field='Hiển thị Giờ', type='ordinal', title='Mốc thời gian', sort=None)
    
    line = alt.Chart(df).mark_line(color='#FF4B4B', strokeWidth=2.5).encode(
        x=x_axis,
        y=alt.Y(field='Nhiệt độ (°C)', type='quantitative', title='Nhiệt độ (°C)')
    )
    
    points = alt.Chart(df).mark_circle(color='#B71C1C', size=60).encode(
        x=x_axis,
        y=alt.Y(field='Nhiệt độ (°C)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )
    
    return alt.layer(line, points).properties(height=180).interactive().configure_axis(labelAngle=0)


def draw_humidity_chart(df):
    if df.empty: 
        return alt.Chart(pd.DataFrame()).mark_blank()
    
    x_axis = alt.X(field='Hiển thị Giờ', type='ordinal', title='Mốc thời gian', sort=None)
    
    line = alt.Chart(df).mark_line(color='#0068C9', strokeWidth=2.5).encode(
        x=x_axis,
        y=alt.Y(field='Độ ẩm (%)', type='quantitative', title='Độ ẩm (%)')
    )
    
    points = alt.Chart(df).mark_circle(color='#0D47A1', size=60).encode(
        x=x_axis,
        y=alt.Y(field='Độ ẩm (%)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )
    
    return alt.layer(line, points).properties(height=180).interactive().configure_axis(labelAngle=0)


def draw_combined_temp_humidity_chart(df):
    """
    Gộp biểu đồ Nhiệt độ và Độ ẩm lồng nhau sử dụng cấu trúc hai trục độc lập (Dual Axis)
    """
    if df.empty:
        return alt.Chart(pd.DataFrame()).mark_blank()

    x_axis = alt.X(field='Hiển thị Giờ', type='ordinal', title='Mốc thời gian', sort=None)

    # Đường và điểm cho Nhiệt độ
    base_temp = alt.Chart(df).encode(x=x_axis)
    line_temp = base_temp.mark_line(color='#FF4B4B', strokeWidth=2.5).encode(
        y=alt.Y(field='Nhiệt độ (°C)', type='quantitative', title='Nhiệt độ (°C)', axis=alt.Axis(titleColor='#FF4B4B'))
    )
    points_temp = base_temp.mark_circle(color='#B71C1C', size=50).encode(
        y=alt.Y(field='Nhiệt độ (°C)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )
    chart_temp = alt.layer(line_temp, points_temp)

    # Đường và điểm cho Độ ẩm
    base_humidity = alt.Chart(df).encode(x=x_axis)
    line_humidity = base_humidity.mark_line(color='#0068C9', strokeWidth=2.5).encode(
        y=alt.Y(field='Độ ẩm (%)', type='quantitative', title='Độ ẩm (%)', axis=alt.Axis(titleColor='#0068C9'))
    )
    points_humidity = base_humidity.mark_circle(color='#0D47A1', size=50).encode(
        y=alt.Y(field='Độ ẩm (%)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )
    chart_humidity = alt.layer(line_humidity, points_humidity)

    # Gộp hai biểu đồ lồng nhau trên trục Y song song độc lập
    combined = alt.independent_charts(
        chart_temp + chart_humidity,
        y='independent'
    ).properties(height=200).interactive()

    return combined.configure_axis(labelAngle=0)
