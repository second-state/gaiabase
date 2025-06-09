import re
import os
import json
import shutil
import textract
from rq import Queue, Retry
from redis import Redis
from pathlib import Path
from firecrawl import FirecrawlApp
from llama_parse import LlamaParse

import html2text
import urllib.request
from bs4 import BeautifulSoup
from http.cookiejar import CookieJar

from sql_query import get_task_info_by_subtask_id, create_subtask, update_subtask
from utils import decrypt_data
from gen_qa_pair import gen_pair

# 初始化 Redis 和队列
redis_conn = Redis()
q_save_url = Queue('step1_save_url', connection=redis_conn)
q_qa = Queue('step2_qa', connection=redis_conn)

FCApp = FirecrawlApp(api_key=os.getenv("FIRECRAWL_KEY"))


# d处理函数
def task_qa(file_path, subtask_id):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            user_input = file.read().strip()
        question_prompt, answer_prompt, split_length, user_config = get_task_info_by_subtask_id(subtask_id)
        decrypt_user_config = decrypt_data(user_config)
        qa_list = gen_pair(
            user_input, subtask_id, question_prompt, answer_prompt,
            decrypt_user_config["chat-base-url"],
            decrypt_user_config["chat-model"],
            decrypt_user_config["chat-api-key"],
            split_length
        )
        output_path = Path(file_path).parent.parent / "qa_files" / f"{Path(file_path).stem}_qa.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(qa_list, f, ensure_ascii=False, indent=2)
        update_subtask(subtask_id, 3,0)
        print(f"已将qa_list保存到: {output_path}")
        return output_path
    except Exception as e:
        update_subtask(subtask_id, 2, -1)
        output_path = Path(file_path).parent.parent / "err_files" / f"{Path(file_path).stem}_err.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(e)
        raise e


# 各类任务
def task_doc(file_path, process_file_path, subtask_id):
    try:
        content = textract.process(file_path).decode("utf-8")
        file_name = os.path.basename(file_path)
        full_path = Path(process_file_path) / f"{file_name}.txt"
        Path(process_file_path).mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as file:
            file.write(content)
        update_subtask(subtask_id, 2,0)
        q_qa.enqueue(task_qa, full_path, subtask_id, retry=Retry(max=3))
        print(f"[log] doc文件处理完成: {full_path}")
        return full_path
    except Exception as e:
        update_subtask(subtask_id, 1,-1)
        print(f"[error] doc处理失败! \n 文件名：{file_path} \n 原因： {e}")
        raise e


def task_pdf(file_path, process_file_path, subtask_id):
    try:
        file_name = os.path.basename(file_path)
        parser = LlamaParse(
            api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
            result_type="markdown",
            num_workers=8,
            verbose=True
        )
        total_text = ""
        extra_info = {"file_name": file_name}
        with open(file_path, "rb") as f:
            documents = parser.load_data(f, extra_info=extra_info)
            texts = [data.text for data in documents]
            total_text = "\n".join(texts)
        output_path = Path(process_file_path) / f"{file_name}.md"
        Path(process_file_path).mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f_out:
            f_out.write(total_text)
        update_subtask(subtask_id, 2,0)
        q_qa.enqueue(task_qa, output_path, subtask_id, retry=Retry(max=3))
        print(f"[log] pdf处理完成: {file_path}")
        return output_path
    except Exception as e:
        update_subtask(subtask_id, 1,-1)
        print(f"[error] pdf处理失败! \n 文件名：{file_path} \n 原因： {e}")


def crawl_url(host_url, process_file_path):
    try:
        map_url_list = FCApp.map_url(host_url)
        for url in map_url_list.links:
            q_save_url.enqueue(task_url, url, process_file_path, retry=Retry(max=3))
        print(f"[log] 爬取url完成: {host_url} -> {len(map_url_list.links)} urls")
        return map_url_list
    except Exception as e:
        print(f"[error] 爬取url失败! \n host_url：{host_url} \n 原因： {e}")
        raise e


def task_url(url, process_file_path):
    sanitized_url = re.sub(r'[\/:*?"<>|]', '_', url)
    first_dir = Path(process_file_path).parts[0]
    subtask_id = create_subtask(first_dir, url, sanitized_url, 2)
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
        output_path = Path(process_file_path) / f"{sanitized_url}.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(plain_text)
            print(f"[log] 解析url处理完成: {url} -> {output_path}")
        update_subtask(subtask_id, 2,0)
        q_qa.enqueue(task_qa, output_path, subtask_id, retry=Retry(max=3))
        return output_path
    except Exception as e:
        update_subtask(subtask_id, 1,-1)
        print(f"[error] url处理失败! \n url：{url} \n 原因： {e}")
        raise e


def task_txt(src_path, dest_dir, subtask_id):
    print("进来了")
    try:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / f"{Path(src_path).name}.txt"
        shutil.copy2(src_path, dest_path)
        update_subtask(subtask_id, 2,0)
        q_qa.enqueue(task_qa, dest_path, subtask_id, retry=Retry(max=3))
        print(f"[log] 文本文件已复制到: {dest_path}")
        return dest_path
    except Exception as e:
        update_subtask(subtask_id, 1,-1)
        print(f"[error] 文件复制失败！\n源文件：{src_path}\n原因：{e}")
        raise e


def task_md(src_path, dest_dir):
    try:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / f"{Path(src_path).name}.md"
        shutil.copy2(src_path, dest_path)

        print(f"[log] md文件已复制到: {dest_path}")
        return dest_path
    except Exception as e:
        print(f"[error] md复制失败！\n源文件：{src_path}\n原因：{e}")
        raise e
