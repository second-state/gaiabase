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


def delete_subtask(subtask_id):
    conn = create_connection()
    if conn is None:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       DELETE FROM `subtask`
                       WHERE id = %s;
                       """, (subtask_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"Delete subtask failed and rolled back. Error: {e}")
        conn.rollback()
        return False
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


def get_subtask_id_by_uuid_and_name(uuid, name):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT id
                       FROM `subtask`
                       WHERE task_id = %s AND save_name = %s;
                       """, (uuid, name,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Error as e:
        print(f"Get subtask id by uuid and name failed. Error: {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_subtask(subtask_id, step=None, status=None, embed_status=None, tidb_status=None):
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
        if embed_status is not None:
            updates.append("embed_status = %s")
            params.append(status)
        if tidb_status is not None:
            updates.append("tidb_status = %s")
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
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
                       SELECT *
                       FROM `subtask`
                       WHERE task_id = %s;
                       """, (uuid,))
        subtasks = cursor.fetchall()

        for subtask in subtasks:
            subtask_id = subtask['id']
            # 使用同样的dictionary=True cursor，或者创建新的dictionary cursor
            cursor.execute("""
                           SELECT status FROM embed_task WHERE subtask_id = %s;
                           """, (subtask_id,))
            embed_results = cursor.fetchall()

            # 现在可以用字段名访问
            embed_statuses = [row['status'] for row in embed_results]

            embed_status = None
            if embed_statuses:
                if 0 in embed_statuses:
                    embed_status = 0
                elif -1 in embed_statuses:
                    embed_status = -1
                elif all(s == 1 for s in embed_statuses):
                    embed_status = 1

            subtask['embed_status'] = embed_status

            cursor.execute("""
                           SELECT status FROM tidb_task WHERE subtask_id = %s;
                           """, (subtask_id,))
            tidb_results = cursor.fetchall()

            # 现在可以用字段名访问
            tidb_statuses = [row['status'] for row in tidb_results]

            tidb_status = None
            if tidb_statuses:
                if 0 in tidb_statuses:
                    tidb_status = 0
                elif -1 in tidb_statuses:
                    tidb_status = -1
                elif all(s == 1 for s in tidb_statuses):
                    tidb_status = 1
            subtask['tidb_status'] = tidb_status

        return subtasks
    except Error as e:
        print(f"Get subtask id by uuid failed. Error: {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def get_embed_and_tidb_id_by_subtask_id(subtask_id):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
                          SELECT embed_id
                            FROM `embed_task`
                            WHERE subtask_id = %s;
                          """, (subtask_id,))
        embed_result = cursor.fetchall()
        cursor.execute("""
                          SELECT tidb_id
                            FROM `tidb_task`
                            WHERE subtask_id = %s;
                          """, (subtask_id,))
        tidb_result = cursor.fetchall()
        if embed_result and tidb_result:
            return {
                'tidb_ids': [row['tidb_id'] for row in tidb_result],
                'embed_ids': [row['embed_id'] for row in embed_result]
            }
        else:
            return None
    except Error as e:
        print(f"Get embed and tidb id by subtask id failed. Error: {e}")
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def create_embed_task(subtask_id, embed_id):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       INSERT INTO `embed_task` (`embed_id`, `subtask_id`)
                       VALUES (%s, %s);
                       """, (embed_id, subtask_id,))
        conn.commit()
        print(cursor.lastrowid)
        return cursor.lastrowid
    except Error as e:
        print(f"Create embed task failed and rolled back. Error: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def create_tidb_task(subtask_id):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       INSERT INTO `tidb_task` (`subtask_id`)
                       VALUES (%s);
                       """, (subtask_id,))
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        print(f"Create tidb task failed and rolled back. Error: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_embed_task_status(embed_task_id, status):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       UPDATE `embed_task`
                       SET status = %s
                       WHERE embed_id = %s;
                       """, (status, embed_task_id))
        conn.commit()
        return embed_task_id
    except Error as e:
        print(f"Update embed task status failed and rolled back. Error: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_tidb_task_status(tidb_task_id, tidb_id, status):
    conn = create_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       UPDATE `tidb_task`
                       SET status = %s, tidb_id = %s
                       WHERE id = %s;
                       """, (status, tidb_id, tidb_task_id))
        conn.commit()
        return tidb_task_id
    except Error as e:
        print(f"Update tidb task status failed and rolled back. Error: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()