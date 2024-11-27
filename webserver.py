import nest_asyncio
import os
import random
import re
import string
import textract
import threading
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from flask import Flask, render_template, request, jsonify
from llama_parse import LlamaParse
from werkzeug.utils import secure_filename

load_dotenv()

FCApp = FirecrawlApp(api_key=os.getenv("FIRECRAWL_KEY"))

app = Flask(__name__)
upload_folder = "uploads"

nest_asyncio.apply()


def create_dir(output_folder=None):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    letters = string.ascii_letters + string.digits
    if not output_folder:
        output_folder = ''.join(random.choice(letters) for _ in range(6)) + timestamp
    os.makedirs(output_folder)
    return output_folder


@app.route("/")
def index():
    return render_template("index.html")


def prase_pdf(input_file, output_folder):
    parser = LlamaParse(
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        result_type="markdown",
        num_workers=8,
        verbose=True
    )

    file_name = os.path.basename(input_file)

    extra_info = {"file_name": file_name}

    with open(input_file, "rb") as f:
        documents = parser.load_data(f, extra_info=extra_info)
        output_file = os.path.join(output_folder, os.path.basename(input_file) + ".md")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(documents[0].text)
            print(f"文件内容已保存到: {output_file}")


def prase_doc(input_file, output_folder):
    content = textract.process(input_file).decode("utf-8")

    output_file = os.path.join(output_folder, os.path.basename(input_file) + ".txt")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"文件内容已保存到: {output_file}")


def crawl_web(url, output_folder):
    crawl_status = FCApp.crawl_url(
        url,
        params={
            'limit': 10000,
            'scrapeOptions': {'formats': ['markdown']}
        },
        poll_interval=30
    )
    print(crawl_status)
    for data in crawl_status['data']:
        sanitized_url = re.sub(r'[\/:*?"<>|]', '_', data['metadata']['url'])
        output_file = os.path.join(output_folder, os.path.basename(sanitized_url) + ".md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(data['markdown'])
            print(f"文件内容已保存到: {output_file}")


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
    print("output_folder")
    print(output_folder)
    for file in files:
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        file_extension = filename.rsplit('.', 1)[-1].lower()

        if file_extension in ['doc', 'docx']:
            prase_doc(file_path, output_folder)
            print(f"{filename} 是doc")
        elif file_extension in ['pdf']:
            prase_pdf(file_path, output_folder)
            print(f"{filename} 是pdf")
        elif file_extension in ['txt']:
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


@app.route("/submit_qa", methods=["POST"])
def submit_qa():
    qa_list = request.json.get("qa_list", [])
    return jsonify({"message": "QA pairs received", "qa_list": qa_list})


if __name__ == "__main__":
    app.run(debug=True)
