import sqlite3
import os
from datetime import datetime
import matplotlib.pyplot as plt

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

def weekly_report():
    """周报"""
    total_record_list = get_focus_records()
    date = datetime.now().strftime("%Y-%m-%d")
    """从date往前推7天,可能跨月份,找出这7天的记录,记录的时间在record["date"]中,str,y-m-d-h,找出七天,如果不足七天,就不足七天,找出前n天(n<=7)"""
    focus_time = []
    for i in range(7):
        date = date_scrollation(date)
        daily_focus_time = 0
        daily_focus_count = 0
        for record in total_record_list:
            if date in record["date"]:
                daily_focus_time += record["focus_time"]
                daily_focus_count += 1
        focus_time.append((date,
                            daily_focus_time,
                            daily_focus_count,
                            int(daily_focus_time/daily_focus_count) if daily_focus_count else 0))
    return focus_time
def day_time_table():
    """习惯表，展示专注时间在一天中的分布，全局统计，可以看出时间段最经常专注"""
    total_record_list = get_focus_records()
    focus_table = []
    for record in total_record_list:
        record["date"] = record["date"].split("-")[-1]
        focus_table.append(record)
    for i in range(24):
        focus_time = 0
        focus_count = 0
        for record in focus_table:
            print(record["date"],type(record["date"]),int(record["date"]))
            if record["date"] == i:
                focus_time += record["focus_time"]
                focus_count += 1
        focus_table.append((i,
                            focus_time,
                            focus_count,
                            int(focus_time/focus_count) if focus_count else 0))
    return focus_table

# 示例用法
if __name__ == "__main__":
    # init_db()  # 初始化数据库
    # add_focus_record(150)  # 添加记录
    # records = get_focus_records()  # 获取记录
    # print(records)  # 打印记录
    print(calculate_total_time())
    print(weekly_report())
    print(day_time_table())
