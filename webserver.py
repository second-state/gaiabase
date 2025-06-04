import base64
import json
import requests
import fitz
import textract
import tempfile
from io import BytesIO

import nest_asyncio
import os
import random
import string
import threading

from rq import Queue, Retry
from redis import Redis
from pathlib import Path

from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from flask import Flask, render_template, request, jsonify, send_from_directory, render_template_string, abort
from flask_socketio import SocketIO

from sql_query import *
from file_utils import *
from save_tidb import save_txt_to_tidb
from gen_embed import gen_embed
from process_file_task import *
from query_function import *

from utils import *

import logging

load_dotenv()

clients = {}

FCApp = FirecrawlApp(api_key=os.getenv("FIRECRAWL_KEY"))

app = Flask(__name__)
socketio = SocketIO(app)
max_concurrent_requests = 2
semaphore = threading.Semaphore(max_concurrent_requests)
upload_folder = "uploads"

redis_conn = Redis()
q_process_doc = Queue('step1_process_doc', connection=redis_conn)
q_process_pdf = Queue('step1_process_pdf', connection=redis_conn)
q_process_txt = Queue('step1_process_txt', connection=redis_conn)
q_gen_embed = Queue('step3_gen_embed', connection=redis_conn)
q_save_tidb = Queue('step3_save_tidb', connection=redis_conn)

nest_asyncio.apply()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/config")
def config():
    return render_template("config.html")


@app.route("/process")
def process():
    return render_template("process.html")


@app.route("/review")
def review():
    return render_template("review.html")


@app.route("/status")
def status():
    return render_template("status.html")


@app.route("/api/encrypt", methods=["POST"])
def encrypt_route():
    try:
        obj = request.get_json()
        encrypted = encrypt_data(obj)
        return jsonify({"encrypted": encrypted})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/decrypt", methods=["POST"])
def decrypt_route():
    try:
        data = request.get_json().get("encrypted")
        decrypted = decrypt_data(data)
        return jsonify({"decrypted": decrypted})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def create_collection(qdrant_url, qdrant_key, collection_name, vector_size):
    payload = json.dumps({
        "vectors": {
            "size": vector_size,
            "distance": "Cosine"
        }
    })
    headers = {
        'api-key': qdrant_key,
        'Content-Type': 'application/json'
    }

    response = requests.request("PUT", qdrant_url + f"/collections/{collection_name}", headers=headers, data=payload)

    if response.status_code != 200 and response.status_code != 409:
        raise Exception(f"Failed to create collection: {response.status_code} - {response.text}")


@app.route("/api/createQdrantCollection", methods=["POST"])
def create_qdrant_collection():
    try:
        data = request.get_json()
        qdrant_url = data.get("qdrant_url")
        qdrant_api_key = data.get("qdrant_api_key")
        collection_name = data.get("collection_name")
        vector_size = int(data.get("vector_size"))
        if not collection_name:
            return jsonify({"error": "Collection name is required"}), 400

        create_collection(qdrant_url, qdrant_api_key, collection_name, vector_size)
        return jsonify({"message": f"Collection '{collection_name}' created successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/getFileCount", methods=["POST"])
def get_file_count():
    result_array = []
    files = request.files.getlist("files[]")

    for file in files:
        file_bytes = file.read()
        if file.filename.lower().endswith('.doc') or file.filename.lower().endswith('.docx'):
            filename = file.filename.lower()
            ext = os.path.splitext(filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                content = textract.process(tmp_path).decode("utf-8")
            finally:
                os.remove(tmp_path)
            print(content)
            result_array.append({
                "file_name": file.filename,
                "file_size": len(content)
            })
        elif file.filename.lower().endswith('.pdf'):
            file_stream = BytesIO(file_bytes)
            doc = fitz.open(stream=file_stream, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            result_array.append({
                "file_name": file.filename,
                "file_size": len(text)
            })
    return jsonify({"files": result_array})


def save_all_file(files, uuid):
    for file_object in files:
        print(file_object)
        file = file_object["file"]
        filename = file.filename
        file_extension = filename.rsplit('.', 1)[-1].lower()
        save_file_path = os.path.join(uuid, "original_files")
        save_file_path = Path(save_file_path) / filename
        subtask_id = create_subtask(uuid, filename, filename, 1)
        file.save(save_file_path)
        update_subtask(uuid, None, 1)
        process_file_path = os.path.join(uuid, "processed_files")
        if file_extension in ['doc', 'docx']:
            q_process_doc.enqueue(task_doc, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))
            print(f"{filename} 是doc")
        elif file_extension in ['pdf']:
            q_process_pdf.enqueue(task_pdf, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))
            print(f"{filename} 是pdf")
        elif file_extension in ['txt']:
            q_process_txt.enqueue(task_txt, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))
            print(f"{filename} 是txt")
        elif file_extension in ['md']:
            q_process_txt.enqueue(task_md, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))
            print(f"{filename} 是md")
        else:
            print(f"{filename} 不是有效的文件格式")


def save_all_qa(qa_data, uuid):
    qa_list = []

    for item in qa_data:
        content = item["content"].strip()
        pairs = content.split('\n\n')  # 分割每组 QA
        for pair in pairs:
            lines = pair.strip().split('\n')
            if len(lines) == 2:
                q = lines[0].replace('Q:', '').strip()
                a = lines[1].replace('A:', '').strip()
                qa_list.append([q, a])

    if len(qa_list) > 0:
        qa_file_path = os.path.join(uuid, "qa_files", "Q&A_Input.json")
        subtask_id = create_subtask(uuid, "Q&A Input", "Q&A_Input.json", 4)
        update_subtask(subtask_id, 3, 0)
        with open(qa_file_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(qa_list, ensure_ascii=False, indent=2))


def crawl_all_url(host_url_list, uuid):
    print(host_url_list)
    for host_url in host_url_list:
        process_file_path = os.path.join(uuid, "processed_files")
        q_save_url.enqueue(crawl_url, host_url, process_file_path, retry=Retry(max=3))


def save_all_text(text_list, uuid):
    total_text = "\n".join(f"{item['longText']} {item['shortText']}" for item in text_list)
    if total_text:
        save_file_path = os.path.join(uuid, "original_files", "text_input.txt")
        process_file_path = os.path.join(uuid, "processed_files")
        subtask_id = create_subtask(uuid, "Text Input", "text_input.txt", 3)
        with open(save_file_path, "w", encoding="utf-8") as f:
            f.write(total_text)
        q_process_txt.enqueue(task_txt, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))


@app.route("/api/processingAllData", methods=["POST"])
def processing_all_data():
    # 从 form 中读取 json 字段
    json_str = request.form.get("processingData")
    if not json_str:
        return "Missing JSON data", 400

    try:
        data = json.loads(json_str)
    except Exception as e:
        return f"Invalid JSON: {e}", 400

    queue = data.get("queue", {})
    settings = data.get("settings", {})
    uuid = data.get("uuid")
    configuration = data.get("configuration")

    split_length = settings.get("splitLength")
    question_prompt = settings.get("questionPrompt")
    answer_prompt = settings.get("answerPrompt")

    for sub in ['original_files', 'processed_files', 'qa_files']:
        Path(f'./{uuid}/{sub}').mkdir(parents=True, exist_ok=True)

    create_task(uuid, configuration, question_prompt, answer_prompt, split_length)

    # 处理文件上传
    uploaded_files = []
    i = 0
    while f"file{i}" in request.files:
        file = request.files[f"file{i}"]
        uploaded_files.append({
            "file": file
        })
        i += 1

    save_all_file(uploaded_files, uuid)
    save_all_text(queue.get("texts", []), uuid)
    crawl_all_url(queue.get("urls", []), uuid)
    save_all_qa(queue.get("qas", []), uuid)

    return "Success", 200


@app.route("/api/getAllSubtaskByUuid", methods=["POST"])
def get_all_subtask_by_uuid():
    data = request.get_json()
    uuid = data.get("uuid")
    if not uuid:
        return jsonify({"error": "UUID is required"}), 400

    subtasks = get_subtasks_by_uuid(uuid)
    if not subtasks:
        return jsonify({"error": "No subtasks found for this UUID"}), 404

    return jsonify(subtasks)


@app.route('/api/filesize/<uuid>/<folder_name>/<filename>')
def get_file_size(uuid, folder_name, filename):
    file_path = os.path.join(uuid, folder_name, filename)
    if not os.path.isfile(file_path):
        abort(404, description="File not found.")
    size = os.path.getsize(file_path)
    return jsonify({'filename': filename, 'size_bytes': size})


@app.route('/api/fileContent/<uuid>/<folder_name>/<filename>')
def get_file_content(uuid, folder_name, filename):
    file_path = os.path.join(uuid, folder_name, filename)
    if not os.path.isfile(file_path):
        abort(404, description="File not found.")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except json.JSONDecodeError:
        abort(400, description="File is not valid JSON.")


@app.route('/api/updateJSON/<uuid>/<folder_name>/<filename>', methods=['POST'])
def update_json_file(uuid, folder_name, filename):
    file_path = os.path.join(uuid, folder_name, filename)

    # 验证是否是 .json 文件
    if not filename.endswith('.json'):
        abort(400, description="Only .json files are allowed.")

    # 检查目录是否存在（如果不存在就创建）
    folder_dir = os.path.join(uuid, folder_name)
    os.makedirs(folder_dir, exist_ok=True)

    # 解析 JSON 数据
    new_data = []
    try:
        new_data = request.get_json(force=True)
    except Exception:
        abort(400, description="Invalid or missing JSON data.")

    # 写入文件
    try:
        if new_data and len(new_data) > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success", "message": f"{filename} updated."})
    except Exception as e:
        abort(500, description=f"Failed to write JSON file: {e}")


@app.route('/api/updateSubtask', methods=['POST'])
def update_subtask_route():
    data = request.get_json()
    subtask_id = data.get("subtask_id")
    step = data.get("step")

    if not subtask_id:
        return jsonify({"error": "Subtask ID is required"}), 400

    result = update_subtask(subtask_id, step)
    if result is None:
        return jsonify({"error": "Failed to update subtask"}), 500

    return jsonify({"message": "Subtask updated successfully", "subtask_id": result})


@app.route('/api/runAllEmbed', methods=['POST'])
def run_all_embed():
    data = request.get_json()
    uuid = data.get("uuid")
    task_info = get_task_info(uuid)
    user_config = task_info[3] if task_info else None
    decrypt_user_config = decrypt_data(user_config)
    process_folder_path = os.path.join(uuid, "processed_files")
    for root, dirs, files in os.walk(process_folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            q_save_tidb.enqueue(save_txt_to_tidb, file_path, decrypt_user_config["tidb-url"], decrypt_user_config["qdrant-collection"])
    qa_folder_path = os.path.join(uuid, "qa_files")
    for root, dirs, files in os.walk(qa_folder_path):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        qa_data = json.load(f)
                        for qa in qa_data:
                            q_gen_embed.enqueue(gen_embed, qa[0], qa[1], decrypt_user_config["embedding-base-url"],
                                                decrypt_user_config["embedding-model"],
                                                decrypt_user_config["embedding-api-key"],
                                                decrypt_user_config["qdrant-url"],
                                                decrypt_user_config["qdrant-api-key"],
                                                decrypt_user_config["qdrant-collection"], retry=Retry(max=3))
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    app.run(port=5190, debug=True)
