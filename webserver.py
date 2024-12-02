import json
import nest_asyncio
import os
import random
import re
import requests
import shutil
import string
import textract
import threading
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from flask import Flask, render_template, request, jsonify, send_from_directory, render_template_string
from llama_parse import LlamaParse
from werkzeug.utils import secure_filename
import logging
from sql_query import *

load_dotenv()

log = logging.getLogger('werkzeug')
log.disabled = True

FCApp = FirecrawlApp(api_key=os.getenv("FIRECRAWL_KEY"))

app = Flask(__name__)
upload_folder = "uploads"

nest_asyncio.apply()


def create_dir(output_folder=None):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    letters = string.ascii_letters + string.digits
    if not output_folder:
        output_folder = ''.join(random.choice(letters) for _ in range(6)) + timestamp
    print(f"创建{output_folder}")
    os.makedirs(output_folder)
    create_task(output_folder)
    return output_folder


def split_and_save(text, file_path, max_length=5000):
    parts = []
    while len(text) > max_length:
        split_point = max(text.rfind(delim, 0, max_length) for delim in ['\n', '。', '!', '?', '!', '?', '.'])
        if split_point == -1:
            split_point = max_length
        parts.append(text[:split_point].strip())
        text = text[split_point:].strip()
    if text:
        parts.append(text)

    dir_name, file_name = os.path.split(file_path)
    for i, part in enumerate(parts):
        this_file_path = os.path.join(dir_name, f"${file_name}_{i + 1:03d}.txt")
        with open(this_file_path, 'w', encoding='utf-8') as file:
            file.write(part)
        print(f"[log] 文件已保存: {file_path}")


@app.route("/")
def index():
    return render_template("index.html")


def prase_pdf(input_file, output_folder):
    file_name = os.path.basename(input_file)
    output_file = os.path.join(output_folder, file_name)
    create_subtask(output_folder, file_name)
    try:
        parser = LlamaParse(
            api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
            result_type="markdown",
            num_workers=8,
            verbose=True
        )
        total_text = ""
        extra_info = {"file_name": file_name}
        with open(input_file, "rb") as f:
            documents = parser.load_data(f, extra_info=extra_info)
            for data in documents:
                total_text += data.text
            split_and_save(total_text, output_file)

        update_subtask(output_folder, file_name, 1)
        print(f"[log] pdf处理完成: {output_file}")
    except Exception as e:
        update_subtask(output_folder, file_name, 2)
        print(f"[error] pdf处理失败! \n 文件名：{output_file} \n 原因： {e}")


def prase_doc(input_file, output_folder):
    file_name = os.path.basename(input_file)
    output_file = os.path.join(output_folder, file_name)
    create_subtask(output_folder, file_name)
    try:
        content = textract.process(input_file).decode("utf-8")
        split_and_save(content, output_file)
        update_subtask(output_folder, file_name, 1)
        print(f"[log] doc文件处理完成: {output_file}")
    except Exception as e:
        update_subtask(output_folder, file_name, 2)
        print(f"[error] doc处理失败! \n 文件名：{output_file} \n 原因： {e}")


def prase_text(input_file, output_folder):
    file_name = os.path.basename(input_file)
    output_file = os.path.join(output_folder, os.path.basename(input_file))
    create_subtask(output_folder, file_name)
    try:
        with open(input_file, "r") as f:
            content = f.read()
            split_and_save(content, output_file)
        update_subtask(output_folder, file_name, 1)
        print(f"[log] text文件处理完成: {output_file}")
    except Exception as e:
        update_subtask(output_folder, file_name, 2)
        print(f"[error] txt处理失败! \n 文件名：{output_file} \n 原因： {e}")


def crawl_web(url, output_folder):
    create_subtask(output_folder, url)
    try:
        crawl_status = FCApp.crawl_url(
            url,
            params={
                'limit': 10000,
                'scrapeOptions': {'formats': ['markdown']}
            }
        )
        for data in crawl_status['data']:
            sanitized_url = re.sub(r'[\/:*?"<>|]', '_', data['metadata']['url'])
            output_file = os.path.join(output_folder, os.path.basename(sanitized_url) + ".md")
            split_and_save(data['markdown'], output_file)
        update_subtask(output_folder, url, 1)
    except Exception as e:
        update_subtask(output_folder, url, 2)


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files[]")
    output_folder = request.form.get("trans_id")

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    if not output_folder:
        output_folder = create_dir()
    elif not os.path.exists(output_folder):
        output_folder = create_dir(output_folder)
    for file in files:
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        file_extension = filename.rsplit('.', 1)[-1].lower()

        if file_extension in ['doc', 'docx']:
            thread = threading.Thread(target=prase_doc, args=(file_path, output_folder))
            thread.start()
            print(f"{filename} 是doc")
        elif file_extension in ['pdf']:
            thread = threading.Thread(target=prase_pdf, args=(file_path, output_folder))
            thread.start()
            print(f"{filename} 是pdf")
        elif file_extension in ['txt']:
            thread = threading.Thread(target=prase_text, args=(file_path, output_folder))
            thread.start()
            print(f"{filename} 是txt")
        else:
            print(f"{filename} 不是有效的文件格式")

    return jsonify({"output_folder": output_folder})


@app.route("/submit_url", methods=["POST"])
def submit_url():
    url = request.json.get("url")
    output_folder = request.json.get("trans_id")
    if not output_folder:
        output_folder = create_dir()
    elif not os.path.exists(output_folder):
        output_folder = create_dir(output_folder)
    thread = threading.Thread(target=crawl_web, args=(url, output_folder))
    thread.start()
    return jsonify({"output_folder": output_folder})


def send_req(folder_path, collection_name, content_list):
    if not folder_path:
        create_dir()
    elif not os.path.exists(folder_path):
        create_dir(folder_path)
    all_ok_file = send_file_req(folder_path, collection_name)
    all_ok_req = send_qa_req(folder_path, collection_name, content_list)
    if all_ok_file and all_ok_req:
        update_task(folder_path, 1)
    else:
        update_task(folder_path, 2)


def send_qa_req(folder_path, collection_name, content_list):
    all_ok = True
    short_text_list = ["the question", "the answer"]
    for content_obj in content_list:
        content = content_obj["question"] + " \n" + content_obj["answer"]
        content_len = len(content)
        if content_len < 400:
            try:
                for short_text in short_text_list:
                    url = f"https://code.flows.network/webhook/pCP3LcLmJiaYDgA4vGfl/embed/{collection_name}"
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    payload = json.dumps({
                        "short_text": short_text,
                        "full_text": content
                    })
                    response = requests.request("POST", url, headers=headers, data=payload)
                    this_status = response.status_code
                    if this_status == 200:
                        print(f"[info] QA embed请求成功")
                    else:
                        print(f"[error] QA embed请求失败：\n错误码：{this_status}")
                        all_ok = False
            except Exception as e:
                print(f"[error] QA embed请求失败：\n错误原因：{e}")
                all_ok = False
        else:
            try:
                for short_text in short_text_list:
                    url = f"https://code.flows.network/webhook/pCP3LcLmJiaYDgA4vGfl/summarize_embed/{folder_path}"
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    payload = json.dumps({
                        "short_text": short_text,
                        "full_text": content
                    })
                    response = requests.request("POST", url, headers=headers, data=payload)
                    this_status = response.status_code
                    if this_status == 200:
                        print(f"[info] QA summarize embed请求成功")
                    else:
                        print(f"[error] QA summarize embed请求失败：\n错误码：{this_status}")
                        all_ok = False
            except Exception as e:
                print(f"[error] QA summarize embed请求失败：\n错误原因：{e}")
                all_ok = False
    return all_ok


def send_file_req(folder_path, collection_name):
    all_ok = True
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith('.txt') or filename.endswith('.md'):
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                content_len = len(content)
                payload = json.dumps({
                    "full_text": content
                })
                if content_len < 400:
                    try:
                        url = f"https://code.flows.network/webhook/pCP3LcLmJiaYDgA4vGfl/embed/{collection_name}"
                        headers = {
                            'Content-Type': 'application/json'
                        }
                        response = requests.request("POST", url, headers=headers, data=payload)
                        this_status = response.status_code
                        if this_status == 200:
                            print(f"[info] embed请求成功: {filename}")
                        else:
                            print(f"[error] embed请求失败：\n文件名：{filename}\n错误码：{this_status}")
                            all_ok = False
                    except Exception as e:
                        print(f"[error] embed请求失败：\n文件名：{filename}\n错误原因：{e}")
                        all_ok = False
                else:
                    try:
                        url = f"https://code.flows.network/webhook/pCP3LcLmJiaYDgA4vGfl/summarize_embed/{folder_path}"
                        headers = {
                            'Content-Type': 'application/json'
                        }
                        response = requests.request("POST", url, headers=headers, data=payload)
                        this_status = response.status_code
                        if this_status == 200:
                            print(f"[info] summarize embed请求成功: {filename}")
                        else:
                            print(f"[error] summarize embed请求失败：\n文件名：{filename}\n错误码：{this_status}")
                            all_ok = False
                    except Exception as e:
                        print(f"[error] summarize embed请求失败：\n文件名：{filename}\n错误原因：{e}")
                        all_ok = False
    if all_ok:
        shutil.rmtree(folder_path)
    return all_ok


@app.route("/submit_all_data", methods=["POST"])
def submit_all_data():
    folder_path = request.json.get("trans_id")
    collection_name = request.json.get("collection_name")
    content_list = request.json.get("qa_list")
    thread = threading.Thread(target=send_req, args=(folder_path, collection_name, content_list))
    thread.start()
    return jsonify(success=True)


@app.route('/listFiles/<dirname>')
def file_list(dirname):
    # 获取文件夹中的所有文件
    print(dirname)
    files = os.listdir(dirname)
    files = [f for f in files if os.path.isfile(os.path.join(dirname, f))]  # 只列出文件
    return render_template_string('''
        <h1>{{dirname}}的处理结果</h1>
        <ul>
        {% for file in files %}
            <li><a href="{{ url_for('get_file', dirname=dirname, filename=file) }}">{{ file }}</a></li>
        {% endfor %}
        </ul>
    ''', dirname=dirname, files=files)


@app.route('/files/<dirname>/<filename>')
def get_file(dirname, filename):
    folder = f'./{dirname}'
    return send_from_directory(folder, filename)


@app.route('/sqlApi/createTask', methods=["POST"])
def create_task_serve():
    task_id = request.json.get("task_id")
    create_task(task_id)
    return "abc"


@app.route('/sqlApi/createSubtask', methods=["POST"])
def create_subtask_serve(task_id, file_name):
    task_id = request.json.get("task_id")
    file_name = request.json.get("file_name")
    create_subtask(task_id, file_name)


@app.route('/sqlApi/updateSubtask', methods=["POST"])
def update_subtask_serve():
    task_id = request.json.get("task_id")
    status = request.json.get("status")
    update_subtask(task_id, status)


@app.route('/sqlApi/checkSubtaskStatus')
def check_subtask_status_serve():
    task_id = request.args.get("task_id")
    data = check_subtask_status(task_id)
    return jsonify({'status': 'success', 'data': data}), 200


@app.route('/sqlApi/checkTaskStatus')
def check_task_status_serve():
    task_id = request.args.get("task_id")
    data = check_task_status(task_id)
    return jsonify({'status': 'success', 'data': data}), 200


@app.route('/img/<path:filename>')
def show_image(filename):
    return send_from_directory('img', filename)


if __name__ == "__main__":
    app.run(port=519, debug=True)
