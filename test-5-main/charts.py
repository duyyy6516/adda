import altair as alt
import pandas as pd

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
        title="📈 Biên thiên tổng thể vi khí hậu: Nhiệt độ (°C) & Độ ẩm (%) bám chung trục trái"
    ).configure_axis(
        labelAngle=0
    ).interactive()
    
    return combined_chart
