import json
from pytidb import TiDBClient
from pytidb.schema import TableModel, Field

from sql_query import update_tidb_task_status


def parse_nested_json_file(file_path):
    # 检查文件是否是 .json 结尾
    if not file_path.endswith(".json"):
        return None
        # raise ValueError("文件不是 .json 格式")

    # 读取并解析 JSON 内容
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 构造返回的对象数组
    result = []
    for item in data:
        if isinstance(item, list) and len(item) >= 2:
            result.append({
                "title": item[0],
                "content": f"{item[0]}\n{item[1]}"
            })
        else:
            raise ValueError(f"数据格式错误，期望一个包含至少两个元素的列表，但得到了：{item}")

    return result


def save_txt_to_tidb(file_path, db_url, table_name, tidb_id):
    # 解析 db_url
    import urllib.parse
    parsed = urllib.parse.urlparse(db_url)
    if parsed.scheme != "mysql":
        raise ValueError("仅支持 mysql:// 开头的连接字符串")

    userinfo = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 4000
    dbname = parsed.path.lstrip("/")

    # 连接 TiDB
    db = TiDBClient.connect(
        host=host,
        port=port,
        username=userinfo,
        password=password,
        database=dbname,
    )

    # 定义表结构
    class Chunk(TableModel, table=True):
        __tablename__ = table_name
        id: int = Field(primary_key=True)
        title: str = Field(sa_type="TEXT")
        content: str = Field(sa_type="TEXT")

    # 创建表
    table = db.create_table(schema=Chunk)

    # 创建全文索引（如需要）
    if not table.has_fts_index("content"):
        table.create_fts_index("content")

    # 读取文件内容
    title_and_content = parse_nested_json_file(file_path)
    rows = []
    if title_and_content:
        for idx, item in enumerate(title_and_content, start=1):
            title = item.get("title", "")
            content = item.get("content", "")
            rows.append(Chunk(title=title, content=content))
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        rows.append(Chunk(title="", content=content))

    # 批量插入
    table.bulk_insert(rows)
    update_tidb_task_status(tidb_id, 1, 1)
    print(f"✅ 成功将文件内容写入 `{dbname}.{table_name}`")