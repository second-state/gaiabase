import os
import string
import random
from datetime import datetime
from sql_query import create_task


def create_dir(output_folder=None):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    letters = string.ascii_letters + string.digits
    if not output_folder:
        output_folder = ''.join(random.choice(letters) for _ in range(6)) + timestamp
    print(f"创建{output_folder}")
    os.makedirs(output_folder)
    create_task(output_folder)
    return output_folder


def split_text(text, max_length=5000):
    parts = []
    max_length = int(max_length)
    while len(text) > max_length:
        split_point = max(text.rfind(delim, 0, max_length) for delim in ['\n', '。', '!', '?', '!', '?', '.'])
        if split_point == -1:
            split_point = max_length
        parts.append(text[:split_point].strip())
        text = text[split_point:].strip()
    if text:
        parts.append(text)

    return parts


def save_file(text, file_path, type="txt", full_name=False):
    dir_name, file_name = os.path.split(file_path)
    if full_name:
        file_name_without_ext = file_name
    else:
        file_name_without_ext = os.path.splitext(file_name)[0]
    this_file_path = os.path.join(dir_name, f"{file_name_without_ext}.{type}")
    with open(this_file_path, 'w', encoding='utf-8') as file:
        file.write(text)
    print(f"[log] 文件已保存: {this_file_path}")
