import os

from llama_parse import LlamaParse
import rdflib
import textract
import json
import requests

from sql_query import *
from file_utils import save_file
from query_function import query_summarize


def format_str(text):
    return str(text)


def save_and_summarize_file(total_text, file_name, input_file, output_folder, old_name, semaphore, socketio, question_prompt, answer_prompt, split_length, file_extension="txt"):
    length = len(total_text)
    if length > 400:
        file_name_list = os.path.splitext(os.path.basename(input_file))
        check_status = True
        for i in range(0, len(total_text), split_length):
            output_file = os.path.join(output_folder, file_name_list[0] + f"_{i}" + file_name_list[1])
            save_file(total_text[i:i + split_length], output_file, file_extension)
            data = query_summarize(total_text[i:i + split_length], output_file, old_name, semaphore, socketio, question_prompt, answer_prompt)
            if not data:
                check_status = False
        if check_status:
            update_file_subtask(output_folder, file_name, None, 1)
        else:
            update_file_subtask(output_folder, file_name, None, 2)
    else:
        output_file = os.path.join(output_folder, file_name)
        save_file(total_text, output_file)

def process_pdf(input_file, output_folder, old_name, semaphore, socketio, question_prompt, answer_prompt, split_length):
    file_name = os.path.basename(input_file)
    create_file_subtask(output_folder, file_name, old_name)
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
        print(f"[log] pdf处理完成: {input_file}")
    except Exception as e:
        update_file_subtask(output_folder, file_name, 2)
        print(f"[error] pdf处理失败! \n 文件名：{input_file} \n 原因： {e}")


def process_doc(input_file, output_folder, old_name, semaphore, socketio, question_prompt, answer_prompt, split_length):
    file_name = os.path.basename(input_file)
    create_file_subtask(output_folder, file_name, old_name)
    try:
        content = textract.process(input_file).decode("utf-8")
        save_and_summarize_file(content, file_name, input_file, output_folder, old_name, semaphore, socketio, question_prompt, answer_prompt, split_length)
        print(f"[log] doc文件处理完成: {input_file}")
    except Exception as e:
        update_file_subtask(output_folder, file_name, 2)
        print(f"[error] doc处理失败! \n 文件名：{input_file} \n 原因： {e}")


def process_text(input_file, output_folder, old_name, semaphore, socketio, question_prompt, answer_prompt, split_length):
    file_name = os.path.basename(input_file)
    file_name_without_ext, file_extension = os.path.splitext(file_name)
    create_file_subtask(output_folder, file_name, old_name)
    try:
        with open(input_file, "r") as f:
            content = f.read()
            save_and_summarize_file(content, file_name, input_file, output_folder, old_name, semaphore, socketio, question_prompt, answer_prompt, split_length, file_extension.lstrip('.'))
        print(f"[log] text文件处理完成: {input_file}")
    except Exception as e:
        update_file_subtask(output_folder, file_name, 2)
        print(f"[error] txt处理失败! \n 文件名：{input_file} \n 原因： {e}")


def process_ttl(input_file, output_folder, ttl_type, old_name):
    file_name = os.path.basename(input_file)
    first_name = os.path.splitext(file_name)[0]
    create_file_subtask(output_folder, file_name, old_name)
    try:
        g = rdflib.Graph()

        g.parse(input_file, format='turtle')

        query = """
        SELECT ?subject ?definition ?prefLabel ?comment ?broader WHERE {
            ?subject skos:prefLabel ?prefLabel .
            OPTIONAL { ?subject skos:broader ?broader } .
            OPTIONAL { ?subject skos:definition ?definition } .
            OPTIONAL { ?subject rdfs:comment ?comment } .
    }
        """

        results = g.query(query)

        broader_list = []
        text_list = []

        for raw in results:
            if ttl_type == "md":
                if raw.broader:
                    broader = raw.broader
                    if "github.com" in broader:
                        broader = broader.replace('blob', 'raw')
                    response = requests.get(broader)

                    if response.status_code == 200:
                        md_content = format_str(response.text)
                        if raw.prefLabel:
                            broader_list.append({'short_text': format_str(raw.prefLabel), 'full_text': md_content})
                        if raw.definition:
                            broader_list.append({'short_text': format_str(raw.definition), 'full_text': md_content})
                        if raw.comment:
                            broader_list.append({'short_text': format_str(raw.comment), 'full_text': md_content})
            elif ttl_type == "text":
                combined_text = (format_str(raw.prefLabel) if raw.prefLabel is not None else "") + (format_str(raw.definition) if raw.definition is not None else "") + (format_str(raw.comment) if raw.comment is not None else "")
                if raw.prefLabel:
                    text_list.append({'short_text': format_str(raw.prefLabel), 'full_text': combined_text})
                if raw.definition:
                    text_list.append({'short_text': format_str(raw.definition), 'full_text': combined_text})
                if raw.comment:
                    text_list.append({'short_text': format_str(raw.comment), 'full_text': combined_text})
        if len(broader_list):
            broader_name = first_name + "_broader.json"
            broader_output_file = os.path.join(output_folder, broader_name)
            print(f"[log] ttl文件处理完成: {broader_output_file}")
            save_file(json.dumps(broader_list), broader_output_file, "json")
        if len(text_list):
            text_name = first_name + "_text.json"
            text_output_file = os.path.join(output_folder, os.path.basename(text_name))
            print(f"[log] ttl文件处理完成: {text_output_file}")
            save_file(json.dumps(text_list), text_output_file, "json")
        update_file_subtask(output_folder, file_name, 1)
    except Exception as e:
        update_file_subtask(output_folder, file_name, 2)
        print(f"[error] ttl处理失败! \n 文件名：{file_name} \n 原因： {e}")