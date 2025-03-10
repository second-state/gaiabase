import mariadb
import os
from dotenv import load_dotenv
from mariadb import Error

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST")
mysql_username = os.getenv("MYSQL_USERNAME")
mysql_password = os.getenv("MYSQL_PASSWORD")
mysql_database_name = os.getenv("MYSQL_DATABASE_NAME")

POOL_SIZE = 5  # 连接池的大小


connection_pool =  mariadb.ConnectionPool(
    pool_name="mypool",
    pool_size=POOL_SIZE,
    user=mysql_username,
    password=mysql_password,
    host=MYSQL_HOST,
    database=mysql_database_name
)

def create_connection():
    try:
        conn = connection_pool.get_connection()
        if conn:
            conn.autocommit = False
            return conn
    except Error as e:
        print(f"Error: '{e}'")
        return None

def check_subtask_status(task_id):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                SELECT file_name, subtask_status, word_count FROM `fileSubtask` WHERE task_id = %s;
            """, (task_id,))

        result = cursor.fetchall()

        return result

    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def check_all_file_subtask_status(task_id):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                SELECT file_name, old_name, subtask_status, summarize_status, embed_status, word_count FROM `fileSubtask` WHERE task_id = %s;
            """, (task_id,))

        result = cursor.fetchall()

        return result

    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def check_file_embed_subtask_status(task_id):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                SELECT file_name, embed_status FROM `fileSubtask` WHERE task_id = %s;
            """, (task_id,))

        result = cursor.fetchall()

        return result

    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def check_file_summarize_subtask_status(task_id):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                SELECT file_name, summarize_status, word_count FROM `fileSubtask` WHERE task_id = %s;
            """, (task_id,))

        result = cursor.fetchall()

        return result

    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def check_url_subtask_status(task_id):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                SELECT id, subtask_status
                FROM `urlSubtask` 
                WHERE task_id = %s;
            """, (task_id,))

        result = cursor.fetchall()

        return result

    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def check_crawl_url_subtask_status(task_id):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                SELECT u.id ,c.id, c.subtask_status
                FROM `urlSubtask` u
                JOIN `crawlUrlSubtask` c ON u.id = c.url_id
                WHERE u.task_id = %s;
            """, (task_id,))

        result = cursor.fetchall()

        return result

    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def check_task_status(task_id):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                SELECT task_status FROM `task` WHERE task_id = %s;
            """, (task_id,))

        result = cursor.fetchone()

        return result

    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def create_task(task_id):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO `task` (`task_id`)
            VALUES (%s)
            ON DUPLICATE KEY UPDATE `task_status` = 0;
            """, (task_id,))

        conn.commit()

    except Error as e:
        print(f"Create task failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_task(task_id, status):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                UPDATE `task` SET task_status = %s
                WHERE task_id = %s;
            """, (status, task_id))

        conn.commit()

    except Error as e:
        print(f"Update task failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()



def create_file_subtask(task_id, file_name, old_name):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                INSERT INTO `fileSubtask` (`task_id`, `file_name`, `old_name`)
            VALUES (%s, %s, %s);
            """, (task_id, file_name, old_name))

        conn.commit()

    except Error as e:
        print(f"Create file subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()

def create_url_subtask(task_id, url):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                INSERT INTO `urlSubtask` (`task_id`, `url`)
            VALUES (%s, %s);
            """, (task_id, url))

        conn.commit()

        new_id = cursor.lastrowid

        return new_id

    except Error as e:
        print(f"Create subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def create_crawl_url_subtask(url_id, crawl_url):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                INSERT INTO `crawlUrlSubtask` (`url_id`, `crawl_url`)
            VALUES (%s, %s);
            """, (url_id, crawl_url))

        conn.commit()

        new_id = cursor.lastrowid

        return new_id

    except Error as e:
        print(f"Create subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_subtask(task_id, file_name, status, word_count=0):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                UPDATE `fileSubtask` SET subtask_status = %s, word_count = %s
                WHERE task_id = %s AND file_name = %s;
            """, (status, word_count, task_id, file_name))

        conn.commit()

    except Error as e:
        print(f"Update file subtask status failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_file_subtask(task_id, file_name, subtask_status=None, summarize_status=None, embed_status=None, word_count=None):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        update_query = "UPDATE `fileSubtask` SET"
        params = []

        if subtask_status is not None:
            update_query += " subtask_status = %s,"
            params.append(subtask_status)

        if summarize_status is not None:
            update_query += " summarize_status = %s,"
            params.append(summarize_status)

        if embed_status is not None:
            update_query += " embed_status = %s,"
            params.append(embed_status)

        if word_count is not None:
            update_query += " word_count = %s,"
            params.append(word_count)

        if params:
            update_query = update_query.rstrip(',')

        update_query += " WHERE task_id = %s AND file_name = %s"
        params.extend([task_id, file_name])

        cursor.execute(update_query, params)

        conn.commit()

    except Error as e:
        print(f"Update file all subtask status failed and rolled back. taskId: {task_id} file_name: {file_name} Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_url_subtask(url_id, status, embed_status=0):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                UPDATE `urlSubtask` SET subtask_status = %s, urlSubtask.embed_status = %s
                WHERE id = %s;
            """, (status, embed_status, url_id))

        conn.commit()

    except Error as e:
        print(f"Update url subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_qa_subtask(qa_id, status):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                UPDATE `QASubtask` SET embed_status = %s
                WHERE id = %s;
            """, (status, qa_id))

        conn.commit()

    except Error as e:
        print(f"Update qa subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_crawl_url_subtask(url_id, status, embed_status=0):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                UPDATE `crawlUrlSubtask` SET subtask_status = %s, embed_status = %s
                WHERE id = %s;
            """, (status, embed_status, url_id))

        conn.commit()

    except Error as e:
        print(f"Update crawl url subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()
