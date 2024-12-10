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


def save_file(text, file_path):
    dir_name, file_name = os.path.split(file_path)
    file_name_without_ext = os.path.splitext(file_name)[0]
    this_file_path = os.path.join(dir_name, f"{file_name_without_ext}.txt")
    with open(this_file_path, 'w', encoding='utf-8') as file:
        file.write(text)
    print(f"[log] 文件已保存: {this_file_path}")


@app.route("/")
def index():
    return render_template("index.html")


def prase_pdf(input_file, output_folder, split_length=5000):
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
            save_file(total_text, output_file)

        update_subtask(output_folder, file_name, 1, len(total_text))
        print(f"[log] pdf处理完成: {output_file}")
    except Exception as e:
        update_subtask(output_folder, file_name, 2)
        print(f"[error] pdf处理失败! \n 文件名：{output_file} \n 原因： {e}")


def prase_doc(input_file, output_folder, split_length=5000):
    file_name = os.path.basename(input_file)
    output_file = os.path.join(output_folder, file_name)
    create_subtask(output_folder, file_name)
    try:
        content = textract.process(input_file).decode("utf-8")
        save_file(content, output_file)
        update_subtask(output_folder, file_name, 1, len(content))
        print(f"[log] doc文件处理完成: {output_file}")
    except Exception as e:
        update_subtask(output_folder, file_name, 2)
        print(f"[error] doc处理失败! \n 文件名：{output_file} \n 原因： {e}")


def prase_text(input_file, output_folder, split_length=5000):
    file_name = os.path.basename(input_file)
    output_file = os.path.join(output_folder, os.path.basename(input_file))
    create_subtask(output_folder, file_name)
    try:
        with open(input_file, "r") as f:
            content = f.read()
            save_file(content, output_file)
        update_subtask(output_folder, file_name, 1, len(content))
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
            save_file(data['markdown'], output_file)
        update_subtask(output_folder, url, 1)
    except Exception as e:
        update_subtask(output_folder, url, 2)
        print(f"[error] url处理失败! \n url：{url} \n 原因： {e}")


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files[]")
    output_folder = request.form.get("trans_id")

    file_name_list = []

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    if not output_folder:
        output_folder = create_dir()
    elif not os.path.exists(output_folder):
        output_folder = create_dir(output_folder)
    for file in files:
        filename = file.filename
        file_extension = filename.rsplit('.', 1)[-1].lower()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        letters = string.ascii_letters + string.digits
        random_value = ''.join(random.choice(letters) for _ in range(6)) + timestamp + "." + file_extension
        file_path = os.path.join(upload_folder, random_value)
        file.save(file_path)
        file_name_list.append({"name": filename, "rename": random_value})
        log_file_path = os.path.join(output_folder, 'fileNameComparisonTable.log')
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{filename} -- {random_value}\n")

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
        elif file_extension in ['md']:
            thread = threading.Thread(target=prase_text, args=(file_path, output_folder))
            thread.start()
            print(f"{filename} 是md")
        else:
            print(f"{filename} 不是有效的文件格式")

    return jsonify({"file_name_list": file_name_list})


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


def send_req(folder_path, collection_name, content_list, split_length, summarize_list):
    if not folder_path:
        create_dir()
    elif not os.path.exists(folder_path):
        create_dir(folder_path)
    all_ok_file = send_file_req(folder_path, collection_name, split_length, summarize_list)
    all_ok_req = send_qa_req(collection_name, content_list)
    if all_ok_file and all_ok_req:
        update_task(folder_path, 1)
    else:
        update_task(folder_path, 2)


def send_qa_req(collection_name, content_list):
    all_ok = True
    short_text_list = ["the question", "the answer"]
    log_file_path = os.path.join(collection_name, 'response.log')
    if not os.path.exists(collection_name):
        os.makedirs(collection_name)
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
                        print(f"[info] {collection_name} QA embed请求成功")
                    else:
                        print(f"[error] {collection_name} QA embed请求失败：\n错误码：{this_status}")
                        all_ok = False
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"{collection_name} QA embed:" + content_obj["question"] + "\nresponse:" + response.text + "\n")
            except Exception as e:
                print(f"[error] {collection_name} QA embed请求失败：\n错误原因：{e}")
                all_ok = False
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{collection_name} QA embed:" + content_obj["question"] + "\nerror:" + e + "\n")
        else:
            try:
                for short_text in short_text_list:
                    url = f"https://code.flows.network/webhook/pCP3LcLmJiaYDgA4vGfl/summarize_embed/{collection_name}"
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
                        print(f"[info] {collection_name} QA summarize embed请求成功")
                    else:
                        print(f"[error] {collection_name} QA summarize embed请求失败：\n错误码：{this_status}")
                        all_ok = False
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"{collection_name} QA embed:" + content_obj["question"] + "\nresponse:" + response.text + "\n")
            except Exception as e:
                print(f"[error] {collection_name} QA summarize embed请求失败：\n错误原因：{e}")
                all_ok = False
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{collection_name} QA summarize embed:" + content_obj["question"] + "\nerror:" + e + "\n")
    return all_ok


def query_embed(content, collection_name, filename, this_summarize):
    all_ok = True
    log_file_path = os.path.join(collection_name, 'response.log')
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
                print(f"[info] {collection_name} embed请求成功: {filename}")
            else:
                print(f"[error] {collection_name} embed请求失败：\n文件名：{filename}\n错误码：{this_status}")
                all_ok = False
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{collection_name} file embed:" + filename + f"\nsummarize:{this_summarize}" + "\nresponse:" + response.text + "\n")
        except Exception as e:
            print(f"[error] {collection_name} embed请求失败：\n文件名：{filename}\n错误原因：{e}")
            all_ok = False
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{collection_name} file embed:" + filename + f"\nsummarize:{this_summarize}" + "\nerror:" + e + "\n")
    else:
        try:
            url = f"https://code.flows.network/webhook/pCP3LcLmJiaYDgA4vGfl/summarize_embed/{collection_name}"
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.request("POST", url, headers=headers, data=payload)
            this_status = response.status_code
            if this_status == 200:
                print(f"[info] {collection_name} summarize embed请求成功: {filename}")
            else:
                print(f"[error] {collection_name} summarize embed请求失败：\n文件名：{filename}\n错误码：{this_status}")
                all_ok = False
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{collection_name} file summarize embed:" + filename + f"\nsummarize:{this_summarize}" + "\nresponse:" + response.text + "\n")
        except Exception as e:
            print(f"[error] {collection_name} summarize embed请求失败：\n文件名：{filename}\n错误原因：{e}")
            all_ok = False
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{collection_name} file summarize embed:" + filename + f"\nsummarize:{this_summarize}" + "\nerror:" + e + "\n")
    return all_ok


def send_file_req(folder_path, collection_name, split_length, summarize_list):
    all_ok = True
    if not os.path.exists(collection_name):
        os.makedirs(collection_name)
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        this_summarize = ""
        try:
            for obj in summarize_list:
                if obj["name"] in filename:
                    this_summarize = obj["value"]
                    print(f"{filename}这个文件的总结是：{this_summarize}")
                    break
        except Exception as e:
            print(f"没找到这个文件：{filename}")
        if filename.endswith('.txt') or filename.endswith('.md'):
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                parts = split_text(content, split_length)
                if len(parts) == 1:
                    content = content + "\n" + this_summarize
                    all_ok = all_ok and query_embed(content, collection_name, filename, this_summarize)
                else:
                    for part in parts:
                        all_ok = all_ok and query_embed(part, collection_name, filename, this_summarize)

    return all_ok


@app.route("/submit_all_data", methods=["POST"])
def submit_all_data():
    folder_path = request.json.get("trans_id")
    collection_name = request.json.get("collection_name")
    content_list = request.json.get("qa_list")
    summarize_list = request.json.get("summarize_list")
    split_length = request.json.get("split_length")
    print(split_length)
    thread = threading.Thread(target=send_req, args=(folder_path, collection_name, content_list, split_length, summarize_list))
    thread.start()
    return jsonify(success=True)


@app.route('/listFiles/<dirname>')
def file_list(dirname):
    # 获取文件夹中的所有文件
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
