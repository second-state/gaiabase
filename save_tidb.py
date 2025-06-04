import mariadb
import urllib.parse


def save_txt_to_tidb(file_path, db_url, table_name):
    # 1. 解析 URL
    parsed = urllib.parse.urlparse(db_url)
    if parsed.scheme != "mysql":
        raise ValueError("仅支持 mysql:// 开头的连接字符串")

    userinfo = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 4000
    dbname = parsed.path.lstrip("/")  # 可能为空

    # 2. 初步连接参数（不带 database）
    conn_args = {
        "user": userinfo,
        "password": password,
        "host": host,
        "port": port,
        "ssl": {
            "ssl_ca": "/etc/ssl/certs/ca-certificates.crt"
        }
    }

    # 3. 连接 MariaDB（无数据库）
    conn = mariadb.connect(**conn_args)
    cursor = conn.cursor()

    # 如果有数据库名，尝试创建
    if dbname:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{dbname}`")
        conn.commit()
        cursor.close()
        conn.close()

        # 加上数据库名再连接
        conn_args["database"] = dbname
        conn = mariadb.connect(**conn_args)
        cursor = conn.cursor()

        # 创建表
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                content TEXT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
        conn.commit()

        # 读取文件并写入
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        cursor.execute(f"INSERT INTO `{table_name}` (content) VALUES (%s)", (content,))
        conn.commit()

        print(f"✅ 成功将文件内容写入 `{dbname}.{table_name}`")
        cursor.close()
        conn.close()
    else:
        raise ValueError("连接字符串中未包含数据库名")