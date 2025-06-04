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

connection_pool = mariadb.ConnectionPool(
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


# 主任务相关sql
def create_task(uuid, user_config, question_prompt="", answer_prompt="", split_length=10000):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       INSERT INTO `task` (`uuid`, `question_prompt`, `answer_prompt`, `split_length`, `user_config`)
                       VALUES (%s, %s, %s, %s, %s);
                       """, (uuid, question_prompt, answer_prompt, split_length, user_config,))
        conn.commit()
        return uuid
    except Error as e:
        print(f"Create task failed and rolled back. Error: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def check_task_status(uuid):
    conn = create_connection()
    if conn is None:
        return None

    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT task_step, task_status
                       FROM `task`
                       WHERE uuid = %s;
                       """, (uuid,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(f"Get task status failed. Error: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def get_task_info(uuid):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT question_prompt ,answer_prompt, split_length, user_config
                       FROM `task`
                       WHERE uuid = %s;
                       """, (uuid,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def get_task_info_by_subtask_id(subtask_id):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT t.question_prompt, t.answer_prompt, t.split_length, t.user_config
                       FROM subtask s
                                JOIN task t ON s.task_id = t.uuid
                       WHERE s.id = %s;
                       """, (subtask_id,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(f"Query task info by subtask id failed. Error: {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_task(uuid, step=None, status=None):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        # 构造动态字段更新语句
        updates = []
        params = []
        if step is not None:
            updates.append("task_step = %s")
            params.append(step)
        if status is not None:
            updates.append("task_status = %s")
            params.append(status)
        # 如果没有字段需要更新，直接返回
        if not updates:
            print("No fields to update.")
            return None
        # 拼接更新语句
        update_clause = ", ".join(updates)
        sql = f"UPDATE `task` SET {update_clause} WHERE uuid = %s;"
        params.append(uuid)
        cursor.execute(sql, tuple(params))
        conn.commit()
        return uuid
    except Exception as e:
        print(f"Update task failed and rolled back. Error: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def create_subtask(uuid, original_name, save_name, subtask_source, subtask_step=1):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       INSERT INTO `subtask` (`task_id`, `original_name`, `save_name`, `subtask_source`, `subtask_step`)
                       VALUES (%s, %s, %s, %s, %s);
                       """, (uuid, original_name, save_name, subtask_source, subtask_step,))
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        print(f"Create subtask failed and rolled back. Error: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def check_subtask_status(subtask_id):
    conn = create_connection()
    if conn is None:
        return None

    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT subtask_step, subtask_status
                       FROM `subtask`
                       WHERE id = %s;
                       """, (subtask_id,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(f"Get subtask status failed. Error: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def get_subtask_info(subtask_id):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT original_name ,save_name, subtask_source
                       FROM `subtask`
                       WHERE id = %s;
                       """, (subtask_id,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(f"Check subtask failed and rolled back. Error: {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_subtask(subtask_id, step=None, status=None):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        # 构造动态字段更新语句
        updates = []
        params = []
        if step is not None:
            updates.append("subtask_step = %s")
            params.append(step)
        if status is not None:
            updates.append("subtask_status = %s")
            params.append(status)
        # 如果没有字段需要更新，直接返回
        if not updates:
            print("No fields to update.")
            return None
        # 拼接更新语句
        update_clause = ", ".join(updates)
        sql = f"UPDATE `subtask` SET {update_clause} WHERE id = %s;"
        params.append(subtask_id)
        cursor.execute(sql, tuple(params))
        conn.commit()
        return subtask_id
    except Exception as e:
        print(f"Update task failed and rolled back. Error: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def get_subtasks_by_uuid(uuid):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT *
                       FROM `subtask`
                       WHERE task_id = %s;
                       """, (uuid,))
        result = cursor.fetchall()
        return result
    except Error as e:
        print(f"Get subtask id by uuid failed. Error: {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()