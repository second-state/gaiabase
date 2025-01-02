import os
import re
import threading
import requests
import json
import urllib.request
from http.cookiejar import CookieJar
from bs4 import BeautifulSoup
import html2text

from file_utils import *
from sql_query import *


def query_summarize(content, output_file, old_name, semaphore, socketio):
    with semaphore:
        file_name = os.path.basename(output_file)
        try:
            url = f"https://code.flows.network/webhook/pCP3LcLmJiaYDgA4vGfl/gen_qa"
            headers = {
                'Content-Type': 'application/json'
            }
            payload = json.dumps({
                "full_text": content
            })
            response = requests.request("POST", url, headers=headers, data=payload)
            this_status = response.status_code
            if this_status == 200:
                data = json.loads(response.text)
                if data["status"]:
                    print(f"[info] {file_name} summarize请求成功: {len(data)}")
                    socketio.emit('file_processed', {'qa_list': data, "file_name": file_name, "old_name": old_name})
                    save_file(response.text, output_file, "summarize", True)
                    return data
                else:
                    socketio.emit('file_processed', {'qa_list': {}, "file_name": file_name, "old_name": old_name})
                    print(f"[info] {file_name} summarize请求失败: 状态码: {this_status} return: {data}")
            else:
                socketio.emit('file_processed', {'qa_list': {}, "file_name": file_name, "old_name": old_name})
                print(f"[info] {file_name} summarize请求失败: 状态码:{this_status}")
        except Exception as e:
            socketio.emit('file_processed', {'qa_list': {}, "file_name": file_name, "old_name": old_name})
            print(f"[info] {file_name} summarize请求失败: {e}")


def crawl_web(url_list, output_folder, url_id):
    try:
        all_ok = True
        for urlObj in url_list:
            url = urlObj["url"]
            try:
                req = urllib.request.Request(url, headers={'User-Agent': "Magic Browser"})
                cj = CookieJar()
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                response = opener.open(req)
                html = response.read().decode('utf8', errors='ignore')
                response.close()
                soup = BeautifulSoup(html, "lxml")
                htmltext = soup.encode('utf-8').decode('utf-8', 'ignore')
                h = html2text.HTML2Text()
                h.ignore_images = True
                plain_text = h.handle(htmltext)
                sanitized_url = re.sub(r'[\/:*?"<>|]', '_', urlObj["url"])
                output_file = os.path.join(output_folder, os.path.basename(sanitized_url) + ".md")
                save_file(plain_text, output_file)
                update_crawl_url_subtask(urlObj["id"], 1)
            except Exception as e:
                all_ok = False
                update_crawl_url_subtask(urlObj["id"], 2)
                print(f"[error] url处理失败! \n url：{url} \n 原因： {e}")
        if all_ok:
            update_url_subtask(url_id, 1)
        else:
            update_url_subtask(url_id, 2)
    except Exception as e:
        update_url_subtask(url_id, 2)
        print(f"[error] url处理失败! \n url：{url_id} \n 原因： {e}")


def send_req(folder_path, collection_name, content_list, embed_list, split_length, summarize_list):
    if not folder_path:
        create_dir()
    elif not os.path.exists(folder_path):
        create_dir(folder_path)
    all_ok_file = send_file_req(folder_path, collection_name, split_length, summarize_list)
    all_ok_qa_req = send_qa_req(collection_name, content_list)
    all_ok_embed_req = send_embed_req(collection_name, embed_list)
    if all_ok_file and all_ok_qa_req and all_ok_embed_req:
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
        content = content_obj["question"] + " \n " + content_obj["answer"]
        try:
            for short_text_type in short_text_list:
                if short_text_type == "the question":
                    short_text = content_obj["question"]
                else:
                    short_text = content_obj["answer"]
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
    return all_ok


def send_embed_req(collection_name, embed_list):
    all_ok = True
    log_file_path = os.path.join(collection_name, 'response.log')
    if not os.path.exists(collection_name):
        os.makedirs(collection_name)
    for embed_obj in embed_list:
        try:
            url = f"https://code.flows.network/webhook/pCP3LcLmJiaYDgA4vGfl/embed/{collection_name}"
            headers = {
                'Content-Type': 'application/json'
            }
            payload = json.dumps({
                "short_text": embed_obj["question"],
                "full_text": embed_obj["answer"]
            })
            response = requests.request("POST", url, headers=headers, data=payload)
            this_status = response.status_code
            if this_status == 200:
                print(f"[info] {collection_name} Simple Embed embed请求成功")
            else:
                print(f"[error] {collection_name} Simple Embed embed请求失败：\n错误码：{this_status}")
                all_ok = False
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{collection_name} Simple Embed embed:" + embed_obj["question"] + "\nresponse:" + response.text + "\n")
        except Exception as e:
            print(f"[error] {collection_name} Simple Embed embed请求失败：\n错误原因：{e}")
            all_ok = False
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{collection_name} Simple Embed embed:" + embed_obj["question"] + "\nerror:" + e + "\n")
    return all_ok



def query_embed(content, collection_name, filename, this_summarize):
    all_ok = True
    log_file_path = os.path.join(collection_name, 'response.log')
    payload = json.dumps({
        "full_text": content
    })
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
    return all_ok


def query_embed_json(content, collection_name, filename, this_summarize):
    all_ok = True
    log_file_path = os.path.join(collection_name, 'response.log')
    json_list = json.loads(content)
    for data in json_list:
        payload = json.dumps(data)
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
    return all_ok


def query_embed_summarize(content, collection_name, filename, this_summarize, full_article):
    all_ok = True
    log_file_path = os.path.join(collection_name, 'response.log')
    json_list = json.loads(content)
    for key, value in json_list.items():
        if key != "status":
            payload = json.dumps({
                "short_text": key + " \n " + value,
                "full_text": full_article
            })
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
    return all_ok


def embed_file(filename, folder_path, collection_name, this_summarize):
    file_path = os.path.join(folder_path, filename)
    if filename.endswith('.txt') or filename.endswith('.md'):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            if len(content) <= 400:
                content = content + "\n" + this_summarize
                this_status = query_embed(content, collection_name, filename, this_summarize)
                if this_status:
                    update_file_subtask(folder_path, filename, None, None, 1)
                else:
                    update_file_subtask(folder_path, filename, None, None, 2)
    elif filename.endswith('.json'):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            this_status = query_embed_json(content, collection_name, filename, this_summarize)
            if this_status:
                update_file_subtask(folder_path, filename, None, None, 1)
            else:
                update_file_subtask(folder_path, filename, None, None, 2)
    elif filename.endswith('.summarize'):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            truly_file_name = filename.rstrip(".summarize")
            truly_file_path = os.path.join(folder_path, truly_file_name)
            with open(truly_file_path, 'r', encoding='utf-8') as truly_file:
                truly_content = file.read()
                this_status = query_embed_summarize(content, collection_name, filename, this_summarize, truly_content)
                if this_status:
                    update_file_subtask(folder_path, truly_file_name, None, None, 1)
                else:
                    update_file_subtask(folder_path, truly_file_name, None, None, 2)

    return this_status


def send_file_req(folder_path, collection_name, split_length, summarize_list):
    all_ok = True
    if not os.path.exists(collection_name):
        os.makedirs(collection_name)
    for filename in os.listdir(folder_path):
        this_summarize = ""
        try:
            for obj in summarize_list:
                if obj["name"] in filename:
                    this_summarize = obj["value"]
                    print(f"{filename}这个文件的总结是：{this_summarize}")
                    break
        except Exception as e:
            print(f"没找到这个文件：{filename}")
        this_status = embed_file(filename, folder_path, collection_name, this_summarize)
        all_ok = all_ok and this_status

    return all_ok
