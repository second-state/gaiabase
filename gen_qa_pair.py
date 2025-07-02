import os
import re
import json
import requests

from urllib.parse import urljoin


def complete_url(base_url):
    # 去除末尾的斜杠，防止重复拼接
    base_url = base_url.rstrip('/')

    # 如果已经包含目标路径，则直接返回
    if base_url.endswith('/v1/chat/completions'):
        return base_url

    # 如果只包含 /v1，则补全剩下部分
    if base_url.endswith('/v1'):
        return base_url + '/chat/completions'

    # 其他情况，拼接完整路径
    return urljoin(base_url + '/', 'v1/chat/completions')


def extract_json(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        json_str = match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print("JSON 解析失败:", e)
            jsonlist = []
            # 尝试提取 "question" 和 "answer" 对
            while text:
                # 使用正则表达式匹配 "question" 和 "answer"
                pattern = r'"question"\s*:\s*"(.*?)"\s*,\s*"answer"\s*:\s*"(.*?)"\s*}'
                match = re.search(pattern, text)

                if not match:
                    break

                question = match.group(1)
                answer = match.group(2)

                jsonlist.append({"question": question, "answer": answer})

                # 删除已处理的部分
                text = text[match.end():]

            return json.dumps(jsonlist, indent=4, ensure_ascii=False)
    else:
        print("未找到 JSON 数据")
    return None


def gen_pair(user_input, subtask_id, question_prompt, answer_prompt, base_url="https://qwen7b.gaia.domains/v1", node_model="qwen7b",
                 gaia_api_key=None, split_length=10000, err_output_path=""):
            sys_prompt = os.getenv(
                "SYS_PROMPT",
                f"As a highly skilled assistant, you are tasked with generating as many as possible informative question and answer pairs from the provided text. Craft Q&A pairs that are relevant, accurate, and varied in type (factual, inferential, thematic). Your questions should be engaging, and answers should be concise, both reflecting the text's intent. Aim for a comprehensive dataset that is rich in content and suitable for training language models, balancing the depth and breadth of information without redundancy. When generating questions you need to keep in mind: {question_prompt}; When generating answers you need to keep in mind: {answer_prompt}."
            )

            def split_text(text, length):
                return [text[i:i+length] for i in range(0, len(text), length)]

            all_qa_pairs = []
            user_inputs = split_text(user_input, split_length) if len(user_input) > split_length else [user_input]

            for idx, chunk in enumerate(user_inputs):
                prompt = f"""
                    Here is the user input to work with:
                    
                    ---
                    {chunk}
                    ---
                    
                    Your task is to dissect this text for both granular details and broader themes, crafting as many Q&A pairs as possible. The questions should cover different types: factual, inferential, thematic, etc. Answers must be concise and reflective of the text's intent. Please generate as many question and answers as possible. Provide the results in the following JSON format:
                    {{
                        "qa_pairs": [
                            {{
                                "question": "<Your question>",
                                "answer": "<Your answer>"
                            }}
                            // ... additional Q&A pairs based on text length
                        ]
                    }}
                """

                payload = json.dumps({
                    "model": node_model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt}
                    ]
                })

                headers = {
                    'accept': 'application/json',
                    'Content-Type': 'application/json',
                    **({'Authorization': f'Bearer {gaia_api_key}'} if gaia_api_key else {})
                }

                try:
                    response = requests.post(complete_url(base_url), headers=headers, data=payload)
                    response.raise_for_status()
                    response_data = response.json()
                    content = response_data["choices"][0]["message"]["content"]
                    print(content)
                    content = extract_json(content)
                    print("fixed content:", content)
                    if content:
                        qa_pairs = content.get("qa_pairs", [])
                        print([(qa["question"], qa["answer"]) for qa in qa_pairs])
                        all_qa_pairs.extend([(qa["question"], qa["answer"]) for qa in qa_pairs])
                except Exception as e:
                    print(f"Failed to create chat for chunk {idx}: {e}")
                    if err_output_path:
                        with open(err_output_path, 'w', encoding='utf-8') as f:
                            f.write(str(e))
                    raise e

            return all_qa_pairs if all_qa_pairs else None
