import requests
import json

from urllib.parse import urljoin

import numpy as np

from sql_query import update_embed_task_status


def normalize_vector(vector):
    """归一化向量"""
    norm = np.linalg.norm(vector)  # 计算长度
    if norm == 0:
        return vector  # 零向量无法归一化
    return vector / norm  # 除以长度


def complete_embed_url(base_url):
    # 去除末尾的斜杠，防止重复拼接
    base_url = base_url.rstrip('/')

    # 如果已经包含目标路径，则直接返回
    if base_url.endswith('/v1/embeddings'):
        return base_url

    # 如果只包含 /v1，则补全剩下部分
    if base_url.endswith('/v1'):
        return base_url + '/embeddings'

    # 其他情况，拼接完整路径
    return urljoin(base_url + '/', 'v1/embeddings')


def gen_embed(short_text, full_text, embedding_base_url, embedding_model, embedding_api_key, qdrant_url, qdrant_api_key,
              qdrant_collection, point_id, task_id, subtask_id):
    text = f"{short_text} {full_text}"
    headers = {
        "Authorization": f"Bearer {embedding_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": text,
        "model": embedding_model
    }
    try:
        response = requests.post(
            complete_embed_url(embedding_base_url),
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        embedding = data.get("data", [{}])[0].get("embedding")

        # 插入数据的 URL
        points_url = f"{qdrant_url}/collections/{qdrant_collection}/points"

        headers = {
            "Content-Type": "application/json",
            "api-key": qdrant_api_key
        }

        # 构造要插入的向量数据
        point_payload = {
            "points": [
                {
                    "id": point_id,
                    "vector": normalize_vector(embedding).tolist(),
                    "payload": {
                        "short_text": short_text,
                        "full_text": full_text
                    }
                }
            ]
        }

        # 插入向量
        insert_response = requests.put(points_url, headers=headers, json=point_payload)
        update_embed_task_status(point_id, 1)
        print("Qdrant Response:", insert_response.status_code, insert_response.text)
        return True
    except requests.RequestException as e:
        update_embed_task_status(point_id, -1)
        err_output_path = task_id / "err_files" / f"{subtask_id}_embed_err.txt"
        with open(err_output_path, 'a', encoding='utf-8') as f:
            f.write(str(e))
        print(f"请求或解析嵌入时出错: {e}")
        return None
