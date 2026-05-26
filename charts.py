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
        y=alt.Y(field='y_min_bound', type='quantitative'),
        y2=alt.Y2(field='y_max_bound')
    )
    
    bg_over = alt.Chart(df_chart).mark_area(color='#FFEBEE', opacity=0.8).encode(
        x=x_axis,
        y=alt.Y(field='y_max_bound', type='quantitative'),
        y2=alt.Y2(field='y_roof')
    )

    # 4. Vẽ đường đồ thị chính và các điểm tròn tương tác Tooltip
    line = alt.Chart(df_chart).mark_line(color='#2E7D32', strokeWidth=3.5).encode(
        x=x_axis,
        y=alt.Y(field='VPD (kPa)', type='quantitative', title='Chỉ số VPD (kPa)', scale=alt.Scale(domain=[0, 3.0], clamp=True))
    )
    
    points = alt.Chart(df_chart).mark_circle(color='#1B5E20', size=70).encode(
        x=x_axis,
        y=alt.Y(field='VPD (kPa)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )

    return alt.layer(bg_under, bg_ideal, bg_over, line, points).properties(height=220).interactive().configure_axis(labelAngle=0)


def draw_temp_humidity_combo_chart(df):
    if df.empty: 
        return alt.Chart(pd.DataFrame()).mark_blank()
    
    # Trục X dùng chung
    x_axis = alt.X(field='Hiển thị Giờ', type='ordinal', title='Mốc thời gian', sort=None)
    
    # 1. Trục Y bên trái (Nhiệt độ - Màu đỏ)
    temp_line = alt.Chart(df).mark_line(color='#FF4B4B', strokeWidth=2.5).encode(
        x=x_axis,
        y=alt.Y(field='Nhiệt độ (°C)', type='quantitative', 
                title='Nhiệt độ (°C)', 
                axis=alt.Axis(titleColor='#FF4B4B', labelColor='#FF4B4B'))
    )
    temp_points = alt.Chart(df).mark_circle(color='#B71C1C', size=60).encode(
        x=x_axis,
        y=alt.Y(field='Nhiệt độ (°C)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )
    temp_chart = alt.layer(temp_line, temp_points)
    
    # 2. Trục Y bên phải (Độ ẩm - Màu xanh dương)
    hum_line = alt.Chart(df).mark_line(color='#0068C9', strokeWidth=2.5).encode(
        x=x_axis,
        y=alt.Y(field='Độ ẩm (%)', type='quantitative', 
                title='Độ ẩm (%)', 
                axis=alt.Axis(titleColor='#0068C9', labelColor='#0068C9'))
    )
    hum_points = alt.Chart(df).mark_circle(color='#0D47A1', size=60).encode(
        x=x_axis,
        y=alt.Y(field='Độ ẩm (%)', type='quantitative'),
        tooltip=['Hiển thị Giờ', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'VPD (kPa)', 'Trạng thái']
    )
    hum_chart = alt.layer(hum_line, hum_points)
    
    # 3. Lồng 2 biểu đồ vào nhau với trục Y độc lập
    combo_chart = alt.layer(temp_chart, hum_chart).resolve_scale(
        y='independent'
    ).properties(
        height=220
    ).interactive().configure_axis(labelAngle=0)
    
    return combo_chart
