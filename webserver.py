import base64
import json
import requests
import fitz
import uuid
import textract
import tempfile
from io import BytesIO

import nest_asyncio
import os
import random
import string
import threading

from rq import Queue, Retry
from rq.exceptions import NoSuchJobError
import time
from redis import Redis
from pathlib import Path

from pytidb import TiDBClient
from pytidb.schema import TableModel, Field
from sqlalchemy import MetaData, Table, delete

from datetime import datetime, timedelta
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from flask import Flask, render_template, request, jsonify, send_from_directory, render_template_string, abort, Response, redirect, url_for, session, make_response
from flask_socketio import SocketIO
from urllib.parse import unquote

from sql_query import *
from file_utils import *
from save_tidb import save_txt_to_tidb
from gen_embed import gen_embed
from process_file_task import *
from query_function import *

from authlib.integrations.flask_client import OAuth

from utils import *

import logging

load_dotenv()

clients = {}

FCApp = FirecrawlApp(api_key=os.getenv("FIRECRAWL_KEY"))

app = Flask(__name__)
app.secret_key = "gaiabase"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365 * 100)
socketio = SocketIO(app)
max_concurrent_requests = 2
semaphore = threading.Semaphore(max_concurrent_requests)
upload_folder = "uploads"

redis_conn = Redis()
q_process_doc = Queue('step1_process_doc', connection=redis_conn)
q_process_pdf = Queue('step1_process_pdf', connection=redis_conn)
q_process_txt = Queue('step1_process_txt', connection=redis_conn)
q_qa = Queue('step2_qa', connection=redis_conn)
q_gen_embed = Queue('step3_gen_embed', connection=redis_conn)
q_del_embed = Queue('step5_del_embed', connection=redis_conn)
q_save_tidb = Queue('step3_save_tidb', connection=redis_conn)
q_del_tidb = Queue('step5_del_tidb', connection=redis_conn)

nest_asyncio.apply()


oauth = OAuth(app)

# GitHub
github = oauth.register(
    name='github',
    client_id='Ov23liUN6Fn7nTJaROGt',
    client_secret='ee5fb34090e02116cc01796651a0511b943cb536',
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    userinfo_endpoint='https://api.github.com/user',
    client_kwargs={'scope': 'user:email'},
)

@app.route('/auth/github')
def github_login():
    redirect_uri = url_for('github_callback', _external=True)
    return github.authorize_redirect(redirect_uri)

@app.route('/auth/github/callback')
def github_callback():
    token = github.authorize_access_token()
    resp = github.get('user')
    profile = resp.json()
    # 保存用户信息到会话
    response = make_response(redirect('/'))
    # 创建或更新用户
    user_id = create_user(profile['id'], profile['login'], profile['email'])
    session['user_id'] = user_id
    print(f"outside_user_id: {user_id}")

    response.set_cookie('user_id', str(user_id), httponly=False, max_age=60*60*24*365)
    response.set_cookie('username', profile['login'], httponly=False, max_age=60*60*24*365)

    # 重定向到主页
    return response


@app.route("/auth/logout", methods=["POST"])
def logout():
    # 清除会话数据
    session.clear()

    # 创建响应对象
    response = make_response(jsonify({"status": "success", "message": "已成功退出登录"}))

    # 删除cookie
    response.set_cookie('user_id', '', expires=0)
    response.set_cookie('username', '', expires=0)

    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/config")
def config():
    return render_template("config.html")


@app.route("/tasks")
def tasks():
    return render_template("tasks.html")


@app.route("/process/<string:type>")
def process(type):
    return render_template("process.html", type=type)


@app.route("/url")
def url():
    return render_template("url.html")


@app.route("/review")
def review():
    return render_template("review.html")


@app.route("/status")
def status():
    return render_template("status.html")


@app.route("/api/getAllTasks", methods=["GET"])
def get_all_tasks():
    try:
        print(session['user_id'])
        tasks = get_subtask_info_by_user_id(session['user_id'])
        return jsonify(tasks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

    if response.status_code == 409:
        # 集合已存在，检查配置是否匹配
        get_response = requests.request("GET", qdrant_url + f"/collections/{collection_name}", headers=headers)
        if get_response.status_code == 200:
            collection_info = get_response.json()

            existing_vector_config = collection_info.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
            existing_size = existing_vector_config.get("size")
            existing_distance = existing_vector_config.get("distance")

            if existing_size != vector_size or existing_distance != "Cosine":
                return {"size": existing_size, "distance": existing_distance}
            # 配置匹配，继续执行
            print(f"Collection '{collection_name}' 已存在且配置匹配")
        else:
            raise Exception(f"Failed to retrieve information of existing collection: {get_response.status_code} - {get_response.text}")
    elif response.status_code != 200:
        raise Exception(f"Failed to create collection: {response.status_code} - {response.text}")
    return None


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

        error_collection = create_collection(qdrant_url, qdrant_api_key, collection_name, vector_size)
        if error_collection:
            return jsonify(error_collection), 409
        else:
            return jsonify({"message": f"Collection '{collection_name}' created successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/getFileCount", methods=["POST"])
def get_file_count():
    result_array = []
    files = request.files.getlist("files[]")
    print(files)
    for file in files:
        file_bytes = file.read()
        print(file_bytes)
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


def save_all_file(files, task_id):
    for file_object in files:
        print(file_object)
        file = file_object["file"]
        filename = file.filename
        file_extension = filename.rsplit('.', 1)[-1].lower()
        save_file_path = os.path.join(task_id, "original_files")
        save_file_path = Path(save_file_path) / filename
        save_name = os.path.join(task_id, "process_files", Path(filename).stem)
        file.save(save_file_path)
        process_file_path = os.path.join(task_id, "processed_files")
        if file_extension in ['doc', 'docx']:
            subtask_id = create_subtask(task_id, filename, Path(filename).stem + ".txt", 1)
            update_subtask(subtask_id, None, 1)
            q_process_doc.enqueue(task_doc, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))
            print(f"{filename} 是doc")
        elif file_extension in ['pdf']:
            subtask_id = create_subtask(task_id, filename, Path(filename).stem + ".md", 1)
            update_subtask(subtask_id, None, 1)
            q_process_pdf.enqueue(task_pdf, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))
            print(f"{filename} 是pdf")
        elif file_extension in ['txt']:
            subtask_id = create_subtask(task_id, filename, Path(filename).stem + ".txt", 1)
            update_subtask(subtask_id, None, 1)
            q_process_txt.enqueue(task_txt, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))
            print(f"{filename} 是txt")
        elif file_extension in ['md']:
            subtask_id = create_subtask(task_id, filename, Path(filename).stem + ".md", 1)
            update_subtask(subtask_id, None, 1)
            q_process_txt.enqueue(task_md, save_file_path, process_file_path, subtask_id, retry=Retry(max=3))
            print(f"{filename} 是md")
        else:
            print(f"{filename} 不是有效的文件格式")


def save_all_qa(qa_data, task_id, only_qa=False):
    qa_list = []
    for item in qa_data:
        try:
            qa_list.extend(item["content"])  # 追加多个 [Q, A] 对
        except json.JSONDecodeError as e:
            print(f"跳过无效 JSON: {e}")

    print(qa_list)

    if len(qa_list) > 0:
        qa_file_path = os.path.join(task_id, "qa_files", "Q&A_Input.json")
        subtask_id = create_subtask(task_id, "Q&A Input", "Q&A_Input.json", 4)
        update_subtask(subtask_id, 3, 0)
        with open(qa_file_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(qa_list, ensure_ascii=False, indent=2))
        processed_file_path = os.path.join(task_id, "processed_files", "Q&A_Input.json")
        with open(processed_file_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(qa_list, ensure_ascii=False, indent=2))
        if only_qa:
            handle_embed(task_id)


def crawl_all_url(host_url_list, task_id):
    print(host_url_list)
    for host_url in host_url_list:
        process_file_path = os.path.join(task_id, "crawl_files")
        q_save_url.enqueue(crawl_url, host_url, process_file_path, retry=Retry(max=3))


def save_all_text(text_list, task_id, onliy_text=False):
    for idx, item in enumerate(text_list):
        total_text = f"{item['longText']} {item['shortText']}"
        if total_text:
            save_name = f"{item.get('shortText') or f'Input_Text{idx+1}'}" + ".txt"
            save_file_path = os.path.join(task_id, "original_files", save_name)
            create_subtask(task_id, "Text Input", save_name, 3)
            with open(save_file_path, "w", encoding="utf-8") as f:
                f.write(total_text)
            process_file_path = os.path.join(task_id, "original_files", save_name)
            with open(process_file_path, "w", encoding="utf-8") as f:
                f.write(total_text)
            qa_file_path = os.path.join(task_id, "qa_files", save_name)
            with open(qa_file_path, "w", encoding="utf-8") as f:
                f.write(total_text)

    if onliy_text:
        handle_embed(task_id)


@app.route("/api/crawl_web_file_gen_qa", methods=["POST"])
def crawl_web_file_gen_qa():
    try:
        data = request.get_json()
        task_id = data.get("task_id")
        files = data.get("files", [])

        if not task_id:
            return jsonify({"error": "Task ID is required"}), 400

        if not files:
            return jsonify({"error": "No files provided"}), 400

        print(task_id)
        print(files)

        # 确保目录存在
        crawl_path = os.path.join(task_id, "crawl_files")
        process_path = os.path.join(task_id, "processed_files")
        os.makedirs(crawl_path, exist_ok=True)
        os.makedirs(process_path, exist_ok=True)

        for file_item in files:
            filename = file_item.get("filename")
            subtask_id = file_item.get("subtask_id")
            content = file_item.get("content")
            print(f"Processing file: {filename}, content length: {len(content) if content else 'None'}")

            if not filename or content is None:
                continue

            # 保存到 crawl_files 文件夹
            crawl_file_path = os.path.join(crawl_path, filename)
            with open(crawl_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 复制到 processed_files 文件夹
            process_file_path = os.path.join(process_path, filename)
            with open(process_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 创建子任务并开始生成问答
            update_subtask(subtask_id, None, 2)
            q_qa.enqueue(task_qa, process_file_path, subtask_id, retry=Retry(max=3))

        return jsonify({"message": "Files processed and Q&A generation started"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



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
    task_id = data.get("uuid")
    configuration = data.get("configuration")

    split_length = settings.get("splitLength")
    question_prompt = settings.get("questionPrompt")
    answer_prompt = settings.get("answerPrompt")

    for sub in ['original_files', 'processed_files', 'qa_files', 'crawl_files', 'err_files']:
        Path(f'./{task_id}/{sub}').mkdir(parents=True, exist_ok=True)

    create_task(task_id, configuration, question_prompt, answer_prompt, split_length, session['user_id'])

    # 处理文件上传
    uploaded_files = []
    i = 0
    while f"file{i}" in request.files:
        file = request.files[f"file{i}"]
        uploaded_files.append({
            "file": file
        })
        i += 1


    save_all_file(uploaded_files, task_id)

    texts = queue.get("texts", [])
    urls = queue.get("urls", [])
    qas = queue.get("qas", [])

    save_all_text(texts, task_id, texts and not qas and not urls and not uploaded_files)
    crawl_all_url(urls, task_id)
    save_all_qa(qas, task_id, qas and not texts and not urls and not uploaded_files)

    # 如果只有qa的话，直接跳转到status页面
    if (qas and not urls and not uploaded_files) or (texts and not urls and not uploaded_files):
        return jsonify({"redirect_url": f"/status?id={task_id}"}), 200
    else:
        return jsonify({"message": "Success"}), 200


@app.route("/api/regenerateQAs", methods=["POST"])
def regenerate_qas():
    data = request.get_json()
    task_id = data.get("uuid")
    subtask_id = data.get("subtask_id")
    processed_file_name = data.get("processed_file_name")
    if not task_id:
        return jsonify({"error": "UUID is required"}), 400

    update_subtask(subtask_id, 2, 0)

    processed_file_path = os.path.join(task_id, "processed_files", processed_file_name)
    q_qa.enqueue(task_qa, processed_file_path, subtask_id)
    return jsonify({"message": "Q&As regeneration started"}), 200


@app.route("/api/getAllSubtaskByUuid", methods=["POST"])
def get_all_subtask_by_uuid():
    data = request.get_json()
    task_id = data.get("uuid")
    if not task_id:
        return jsonify({"error": "UUID is required"}), 400

    subtasks = get_subtasks_by_uuid(task_id)
    if not subtasks:
        return jsonify([]), 404

    return jsonify(subtasks)


@app.route('/api/filesize/<task_id>/<folder_name>/<filename>')
def get_file_size(task_id, folder_name, filename):
    file_path = os.path.join(task_id, folder_name, filename)
    if not os.path.isfile(file_path):
        abort(404, description="File not found.")
    size = os.path.getsize(file_path)
    return jsonify({'filename': filename, 'size_bytes': size})


@app.route('/api/fileWords/<task_id>/<folder_name>/<filename>')
def get_file_word_count(task_id, folder_name, filename):
    file_path = os.path.join(task_id, folder_name, filename)
    if not os.path.isfile(file_path):
        abort(404, description="File not found.")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            word_count = len(content)
    except Exception as e:
        abort(500, description=f"Error reading file: {str(e)}")

    return jsonify({'filename': filename, 'char_count': word_count})


@app.route('/api/fileContent/<task_id>/<folder_name>/<filename>')
def get_file_content(task_id, folder_name, filename):
    filename = unquote(filename)
    file_path = os.path.join(task_id, folder_name, filename)
    if not os.path.isfile(file_path):
        abort(404, description="File not found.")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return jsonify(data)
            except json.JSONDecodeError:
                f.seek(0)  # 重置文件指针到开头
                raw_content = f.read()
                return Response(raw_content, mimetype='text/plain')
    except Exception as e:
        return Response(f"Error reading file: {e}", status=500, mimetype='text/plain')


@app.route('/api/updateJSON/<task_id>/<folder_name>/<filename>', methods=['POST'])
def update_json_file(task_id, folder_name, filename):
    file_path = os.path.join(task_id, folder_name, filename)

    # 验证是否是 .json 文件
    if not filename.endswith('.json'):
        abort(400, description="Only .json files are allowed.")

    # 检查目录是否存在（如果不存在就创建）
    folder_dir = os.path.join(task_id, folder_name)
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


def find_corresponding_file(filename, task_id):
    # 去掉 `_qa.json` 得到原始文件名
    if not filename.endswith('_qa.json'):
        return None
    base_name = filename[:-8]  # 去掉 `_qa.json`

    # 判断是否是 pdf 文件的特例
    if base_name.endswith('.pdf'):
        target_name = base_name + '.md'
    else:
        target_name = base_name + '.txt'

    # 构造完整路径
    target_path = os.path.join(task_id, "processed_files", target_name)

    # 检查文件是否存在
    return target_path if os.path.exists(target_path) else None


def wait_for_summary(summary_job, check_interval=5):
    """等待汇总任务完成"""
    print("等待所有任务完成...")

    while not summary_job.is_finished and not summary_job.is_failed:
        print(f"汇总任务状态: {summary_job.get_status()}")
        time.sleep(check_interval)
        summary_job.refresh()  # 刷新任务状态

    if summary_job.is_finished:
        return summary_job.result
    else:
        print(f"汇总任务失败: {summary_job.exc_info}")
        return None


def handle_embed(task_id):
    task_info = get_task_info(task_id)
    user_config = task_info[3] if task_info else None
    decrypt_user_config = decrypt_data(user_config)
    process_folder_path = os.path.join(task_id, "processed_files")
    for root, dirs, files in os.walk(process_folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            subtask_data = get_subtask_id_by_uuid_and_name(task_id, file)
            subtask_id = subtask_data[0]
            print(f"Processing file: {file_path}, Subtask ID: {subtask_id}")
            tidb_subtask_id = create_tidb_task(subtask_id)
            print(f"Created TiDB task with ID: {tidb_subtask_id}")
            q_save_tidb.enqueue(save_txt_to_tidb, file_path, decrypt_user_config["tidb-url"], decrypt_user_config["tidb-table-name"], tidb_subtask_id, task_id, subtask_id)
    qa_folder_path = os.path.join(task_id, "qa_files")
    for root, dirs, files in os.walk(qa_folder_path):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                full_text = ""
                filename = file.replace('_qa.json', '')
                print(f"task_id: {task_id}, filename: {filename}")
                subtask_data = get_subtask_id_by_uuid_and_name(task_id, filename)
                subtask_id = subtask_data[0]
                save_file_data = subtask_data[1]
                print(f"Processing file: {file_path}, Subtask ID: {subtask_id}, Save File Data: {save_file_data}")
                if(save_file_data != "Q&A_Input.json"):
                    with open(os.path.join(task_id, "processed_files", save_file_data), 'r', encoding='utf-8') as f:
                        full_text = f.read()
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        qa_data = json.load(f)
                        for qa in qa_data:
                            if full_text:
                                for i in range(2):
                                    point_id = str(uuid.uuid4())
                                    create_embed_task(subtask_id ,point_id)
                                    if i == 0:
                                        q_gen_embed.enqueue(gen_embed, qa[0], full_text, decrypt_user_config["embedding-base-url"],
                                                            decrypt_user_config["embedding-model"],
                                                            decrypt_user_config["embedding-api-key"],
                                                            decrypt_user_config["qdrant-url"],
                                                            decrypt_user_config["qdrant-api-key"],
                                                            decrypt_user_config["qdrant-collection"], point_id, task_id, subtask_id, retry=Retry(max=3))
                                    else:
                                        q_gen_embed.enqueue(gen_embed, qa[0] + "\n" + qa[1], full_text, decrypt_user_config["embedding-base-url"],
                                                            decrypt_user_config["embedding-model"],
                                                            decrypt_user_config["embedding-api-key"],
                                                            decrypt_user_config["qdrant-url"],
                                                            decrypt_user_config["qdrant-api-key"],
                                                            decrypt_user_config["qdrant-collection"], point_id, task_id, subtask_id, retry=Retry(max=3))
                            else:
                                for text in qa:
                                    point_id = str(uuid.uuid4())
                                    create_embed_task(subtask_id ,point_id)
                                    q_gen_embed.enqueue(gen_embed, text, qa[0] + "\n" + qa[1], decrypt_user_config["embedding-base-url"],
                                                        decrypt_user_config["embedding-model"],
                                                        decrypt_user_config["embedding-api-key"],
                                                        decrypt_user_config["qdrant-url"],
                                                        decrypt_user_config["qdrant-api-key"],
                                                        decrypt_user_config["qdrant-collection"], point_id, task_id, subtask_id, retry=Retry(max=3))
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    return jsonify({"error": f"Error processing {file_path}: {str(e)}"}), 500
            elif file.endswith('.txt'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_data = f.read()
                    point_id = str(uuid.uuid4())
                    subtask_data = get_subtask_id_by_uuid_and_name(task_id, file)
                    subtask_id = subtask_data[0]
                    create_embed_task(subtask_id, point_id)
                    q_gen_embed.enqueue(gen_embed, file, text_data, decrypt_user_config["embedding-base-url"],
                                        decrypt_user_config["embedding-model"],
                                        decrypt_user_config["embedding-api-key"],
                                        decrypt_user_config["qdrant-url"],
                                        decrypt_user_config["qdrant-api-key"],
                                        decrypt_user_config["qdrant-collection"], point_id, task_id, subtask_id, retry=Retry(max=3))
    return jsonify({"status": "success"})


@app.route('/api/runAllEmbed', methods=['POST'])
def run_all_embed():
    data = request.get_json()
    task_id = data.get("uuid")
    return handle_embed(task_id)


@app.route('/api/deleteSubtask/<subtask_id>', methods=['DELETE'])
def get_embed_and_tidb_id(subtask_id):
    if not subtask_id:
        return jsonify({"error": "Subtask ID is required"}), 400

    try:
        task_info = get_task_info_by_subtask_id(subtask_id)
        user_config = task_info[3] if task_info else None
        decrypt_user_config = decrypt_data(user_config)
        id_data = get_embed_and_tidb_id_by_subtask_id(subtask_id)
        url = f"{decrypt_user_config['qdrant-url']}/collections/{decrypt_user_config['qdrant-collection']}/points/delete"

        payload = json.dumps({
            "points": id_data["embed_ids"],
        })
        headers = {
            'api-key': decrypt_user_config['qdrant-api-key'],
            'Content-Type': 'application/json'
        }

        requests.request("POST", url, headers=headers, data=payload)

        parsed = urllib.parse.urlparse(decrypt_user_config["tidb-url"])
        if parsed.scheme != "mysql":
            raise ValueError("仅支持 mysql:// 开头的连接字符串")

        userinfo = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port or 4000
        dbname = parsed.path.lstrip("/")  # 可能为空

        # 连接 TiDB
        db = TiDBClient.connect(
            host=host,
            port=port,
            username=userinfo,
            password=password,
            database=dbname if dbname else "database",
        )

        engine = db.db_engine
        metadata = MetaData()
        table = Table(
            decrypt_user_config["tidb-table-name"],
            metadata,
            autoload_with=engine
        )

        print(f"表名: {table.name}")

        # 删除指定 id 的数据
        if id_data["tidb_ids"]:
            delete_stmt = delete(table).where(table.c.id.in_(id_data["tidb_ids"]))
            db.execute(delete_stmt)

        delete_subtask(subtask_id)
        return jsonify({"status": "success"})
    except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route('/api/getConfig/<task_id>', methods=['GET'])
def get_config(task_id):
    if not task_id:
        return jsonify({"error": "Task ID is required"}), 400

    task_info = get_task_info(task_id)
    if not task_info:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(decrypt_data(task_info[3]))


if __name__ == "__main__":
    app.run(port=5190, debug=True)
