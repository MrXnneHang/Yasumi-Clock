import csv
import os
from datetime import datetime

LOG_FILE = 'pomodoro_log.csv'
FIELDNAMES = [
    'start_time',
    'end_time',
    'session_type',
    'status',
    'planned_duration_minutes',
    'actual_duration_seconds',
    'pause_duration_seconds',
    'pause_count'
]

def log_session(session_data):
    """
    将一次番茄钟会话的数据记录到CSV文件中。

    Args:
        session_data (dict): 包含会话信息的字典，键应与FIELDNAMES匹配。
    """
    file_exists = os.path.isfile(LOG_FILE)

    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)

        if not file_exists:
            writer.writeheader()
        
        writer.writerow(session_data)

if __name__ == '__main__':
    # 这是一个用于测试的例子
    # 实际使用时，这个模块会被其他模块导入并调用 log_session 函数
    print(f"正在测试日志功能，将写入示例数据到 {LOG_FILE}")
    
    test_data = {
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
        'session_type': 'pomodoro',
        'status': 'completed',
        'planned_duration_minutes': 25,
        'actual_duration_seconds': 1500
    }
    log_session(test_data)
    
    test_data_2 = {
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
        'session_type': 'short_break',
        'status': 'interrupted',
        'planned_duration_minutes': 5,
        'actual_duration_seconds': 200
    }
    log_session(test_data_2)
    
    print("测试数据写入完成。")