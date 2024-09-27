import sqlite3
import os
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from scipy.interpolate import make_interp_spline  # For smoothing the line

# 创建数据目录
data_dir = './data'
os.makedirs(data_dir, exist_ok=True)

# 数据库文件路径
db_name = os.path.join(data_dir, 'focus.db')

# 初始化数据库并创建表
def init_db():
    if os.path.exists(db_name):
        return
    ## 如果数据库文件不存在，则会自动创建数据库文件
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS focus_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            focus_time INTEGER NOT NULL,
            date TEXT NOT NULL
        );
    ''')
    
    conn.commit()
    conn.close()

# 插入专注记录
def add_focus_record(focus_time, date=None):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d-%H")
        
    if not (0 <= focus_time <= 240):
        raise ValueError("focus_time 必须在 0 到 240 之间")
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO focus_records (focus_time, date) VALUES (?, ?)",
        (focus_time, date)
    )
    
    conn.commit()
    conn.close()


# 读取专注记录
def get_focus_records():
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute("SELECT focus_time, date FROM focus_records")
    records = cursor.fetchall()
    
    conn.close()
    
    focus_list = [{"focus_time": row[0], "date": row[1]} for row in records]
    return focus_list

## --------------测试代码---------------

from util import date_scrollation

def calculate_total_time():
    total_record_list = get_focus_records()
    total_time = 0
    for record in total_record_list:
        total_time += record["focus_time"]
    return total_time

# 转换日期格式到datetime的不带多余0的格式。

def date_format(date):
    date = date.split("-")
    return "-".join([str(int(i)) for i in date])

def weekly_report():
    """周报"""
    total_record_list = get_focus_records()
    date = datetime.now().strftime("%Y-%m-%d")
    """从date往前推7天,可能跨月份,找出这7天的记录,记录的时间在record["date"]中,str,y-m-d-h,找出七天,如果不足七天,就不足七天,找出前n天(n<=7)"""
    focus_time = []
    for i in range(7):
        date = date_scrollation(date)
        day_time = 0
        day_count = 0
        night_time = 0
        night_count = 0
        for record in total_record_list:
            if date in date_format(record["date"]):
                hour = record["date"].split("-")[-1]
                if (int(hour) >= 6) and (int(hour)<=17):
                    day_time += record["focus_time"]
                    day_count += 1
                else:
                    night_time += record["focus_time"]
                    night_count += 1 
        focus_time.append({"date": date[5:],
                           "day_time": day_time,
                           "day_count": day_count,
                           "day_average": int(day_time/day_count) if day_count else 0,
                           "night_time": night_time,
                           "night_count": night_count,
                           "night_average": int(night_time/night_count) if night_count else 0})
    return focus_time
def day_time_table():
    """习惯表，展示专注时间在一天中的分布，全局统计，可以看出时间段最经常专注"""
    total_record_list = get_focus_records()
    hour_record = []
    focus_table = []
    for record in total_record_list:
        record["date"] = record["date"].split("-")[-1]
        hour_record.append(record)
    for i in range(24):
        focus_time = 0
        focus_count = 0
        for record in hour_record:
            if int(record["date"]) == i:
                focus_time += record["focus_time"]
                focus_count += 1
        focus_table.append({"hour":i,
                            "focus_time":focus_time,
                            "focus_count":focus_count,
                            "focus_average":int(focus_time/focus_count) if focus_count else 0})
    return focus_table

def plot_focus_report(data):
    """
    Generates a focus report bar chart with a smooth curve overlay for total focus time.

    :param data: List of dictionaries containing 'date', 'day_time', 'night_time', 'day_count', and 'night_count'.
    """
    # Convert the list of dictionaries into a pandas DataFrame
    df = pd.DataFrame(data)

    # Create figure and axis
    fig, ax = plt.subplots()

    # Create stacked bars for day and night time with transparency and border
    bar_width = 0.75  # Increase the bar width for thicker bars
    index = np.arange(len(df['date']))

    # Specify colors using RGB tuples
    day_color = (0.3, 0.8, 0.3)    # Green with RGB
    night_color = (0, 0.6, 0.9)  # Dark Blue with RGB
    curve_color = (0,0,0)  # Orange with RGB

    # Draw the day bars with transparency and edgecolor
    day_bars = ax.bar(index, df['day_time'], bar_width, 
                      label='Day Time', 
                      color=day_color, alpha=0.3,  # Transparent body
                      edgecolor=day_color, linewidth=2)  # Opaque border
    
    # Draw the night bars with transparency and edgecolor
    night_bars = ax.bar(index, df['night_time'], bar_width, 
                        bottom=df['day_time'], 
                        label='Night Time', 
                        color=night_color, alpha=0.5,  # Transparent body
                        edgecolor=night_color, linewidth=2)  # Opaque border

    # Overlay the smooth curve (trend line)
    total_time = df['day_time'] + df['night_time']

    # Interpolation for smooth line
    xnew = np.linspace(index.min(), index.max(), 300)  # More points for smoothness
    spl = make_interp_spline(index, total_time, k=3)  # Smooth line with cubic spline
    total_time_smooth = spl(xnew)

    # Use RGB color for the curve
    ax.plot(xnew, total_time_smooth, color=curve_color, linestyle='-', marker='', linewidth=2)

    # Limit the y-axis so the highest bar does not exceed 75% of the plot
    max_total_time = total_time.max()
    ax.set_ylim(0, max_total_time * 1.33)  # 1.33 is approximately 4/3, so the max height is 75% of total

    # Add labels, title, and legend
    ax.set_xlabel('Date')
    ax.set_ylabel('Focus Time (hours)')
    ax.set_title('Weekly Focus Report')
    ax.set_xticks(index)
    ax.set_xticklabels(df['date'])
    ax.legend()

    # Show the plot
    plt.tight_layout()
    plt.show()

def plot_focus_habit(data):
    """
    Generates a horizontal heatmap representing the user's focus habit over 24 hours.

    :param data: List of dictionaries containing 'hour', 'focus_time', 'focus_count', and 'focus_average'.
    """
    # Extract the focus times for each hour
    hours = np.arange(24)
    focus_times = np.array([entry['focus_time'] for entry in data])

    # Find the maximum focus time for normalization
    max_focus_time = focus_times.max()

    # Map the focus times to alpha values between 0.01 and 1
    if max_focus_time > 0:
        alphas = 0.01 + (focus_times / max_focus_time) * (1 - 0.05)
    else:
        alphas = np.full_like(focus_times, 0.05)  # Handle the case when all focus_time is 0

    # Create a figure and axis
    fig, ax = plt.subplots(figsize=(12, 2))  # Horizontal figure


    # Define a fixed RGB color (blue)
    rgb_color = (0, 0.6, 0.9)  # Blue color in RGB

    # Draw 24 horizontal blocks with edgecolor and alpha for transparency
    for i in range(24):
        # Use fill_between to create each block with a transparent fill and solid border
        ax.fill_between([i, i + 1], 0, 1, color=rgb_color, alpha=alphas[i],
                        edgecolor='black', linewidth=2)  # Opaque black border

    # Set the limits and labels
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 1)
    ax.set_xticks(hours + 0.5)  # Set labels in the center of each block
    ax.set_xticklabels([f'{hour}:00' for hour in hours], rotation=90)
    ax.set_yticks([])  # No y-axis ticks for a clean look

    # Add title
    ax.set_title('User Focus Habit Over 24 Hours', fontsize=16)

    # Show the plot
    plt.tight_layout()
    plt.show()

# 示例用法
if __name__ == "__main__":
    # init_db()  # 初始化数据库
    # add_focus_record(150)  # 添加记录
    
    # records = get_focus_records()  # 获取记录
    # print(records)
    print(calculate_total_time())
    plot_focus_report(weekly_report())
    plot_focus_habit(day_time_table())
