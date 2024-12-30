import nest_asyncio
import os
import random
import string
import threading

from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from flask import Flask, render_template, request, jsonify, send_from_directory, render_template_string
from flask_socketio import SocketIO

from sql_query import *
from file_utils import *
from process_file import *
from query_function import *

import logging

load_dotenv()

clients = {}

log = logging.getLogger('werkzeug')
log.disabled = True

FCApp = FirecrawlApp(api_key=os.getenv("FIRECRAWL_KEY"))

app = Flask(__name__)
socketio = SocketIO(app)
max_concurrent_requests = 2
semaphore = threading.Semaphore(max_concurrent_requests)
upload_folder = "uploads"

nest_asyncio.apply()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/task")
def task():
    task_id = request.args.get('task_id')
    return render_template("index.html", task_id=task_id)


@app.route("/embed")
def embed():
    task_id = request.args.get('task_id')
    return render_template("embed.html", task_id=task_id)


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files[]")
    output_folder = request.form.get("trans_id")
    ttl_type = request.form.get("ttl_type")

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
            thread = threading.Thread(target=process_doc, args=(file_path, output_folder, filename, semaphore, socketio))
            thread.start()
            print(f"{filename} 是doc")
        elif file_extension in ['pdf']:
            thread = threading.Thread(target=process_pdf, args=(file_path, output_folder, filename, semaphore, socketio))
            thread.start()
            print(f"{filename} 是pdf")
        elif file_extension in ['txt']:
            thread = threading.Thread(target=process_text, args=(file_path, output_folder, filename, semaphore, socketio))
            thread.start()
            print(f"{filename} 是txt")
        elif file_extension in ['md']:
            thread = threading.Thread(target=process_text, args=(file_path, output_folder, filename, semaphore, socketio))
            thread.start()
            print(f"{filename} 是md")
        elif file_extension in ['ttl']:
            thread = threading.Thread(target=process_ttl, args=(file_path, output_folder, ttl_type, filename))
            thread.start()
            print(f"{filename} 是ttl")
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
    url_id = create_url_subtask(output_folder, url)
    map_url_list = FCApp.map_url(url)
    all_links = []
    for data in map_url_list['links']:
        if data != url:
            crawl_url_id = create_crawl_url_subtask(url_id, data)
            all_links.append({"url": data, "id": crawl_url_id})
    thread = threading.Thread(target=crawl_web, args=(all_links, output_folder, url_id))
    thread.start()
    return jsonify({"id": url_id, "mapUrlList": all_links})


@socketio.on('connect')
def handle_connect():
    print("Client connected")


@app.route("/submit_all_data", methods=["POST"])
def submit_all_data():
    folder_path = request.json.get("trans_id")
    collection_name = request.json.get("collection_name")
    content_list = request.json.get("qa_list")
    embed_list = request.json.get("embed_list")
    summarize_list = request.json.get("summarize_list")
    split_length = request.json.get("split_length")
    thread = threading.Thread(target=send_req, args=(folder_path, collection_name, content_list, embed_list, split_length, summarize_list))
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
def create_subtask_serve():
    task_id = request.json.get("task_id")
    file_name = request.json.get("file_name")
    create_file_subtask(task_id, file_name)


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


@app.route('/sqlApi/checkAllFileSubtaskStatus')
def check_file_subtask_status():
    task_id = request.args.get("task_id")
    data = check_all_file_subtask_status(task_id)
    return jsonify({'status': 'success', 'data': data}), 200


@app.route('/sqlApi/checkFileEmbedStatus')
def check_file_embed_status():
    task_id = request.args.get("task_id")
    data = check_file_embed_subtask_status(task_id)
    return jsonify({'status': 'success', 'data': data}), 200


@app.route('/sqlApi/checkUrlSubtaskStatus')
def check_url_subtask_status_serve():
    task_id = request.args.get("task_id")
    data = check_url_subtask_status(task_id)
    return jsonify({'status': 'success', 'data': data}), 200


@app.route('/sqlApi/checkCrawlUrlSubtaskStatus')
def check_crawl_url_subtask_status_serve():
    task_id = request.args.get("task_id")
    data = check_crawl_url_subtask_status(task_id)
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
