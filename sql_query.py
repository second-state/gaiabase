import mariadb
import os
from dotenv import load_dotenv
from mariadb import Error

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST")
mysql_username = os.getenv("MYSQL_USERNAME")
mysql_password = os.getenv("MYSQL_PASSWORD")
mysql_database_name = os.getenv("MYSQL_DATABASE_NAME")


def create_connection():
    """创建并返回数据库连接"""
    try:
        conn = mariadb.connect(
            host=MYSQL_HOST,
            user=mysql_username,
            password=mysql_password,
            database=mysql_database_name,
        )
        if conn.cursor():
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
                SELECT file_name, subtask_status FROM `fileSubtask` WHERE task_id = %s;
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
        print(f"Update subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()



def create_subtask(task_id, file_name):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                INSERT INTO `fileSubtask` (`task_id`, `file_name`)
            VALUES (%s, %s);
            """, (task_id, file_name))

        conn.commit()

    except Error as e:
        print(f"Create subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_subtask(task_id, file_name, status):
    conn = create_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
                UPDATE `fileSubtask` SET subtask_status = %s
                WHERE task_id = %s AND file_name = %s;
            """, (status, task_id, file_name))

        conn.commit()

    except Error as e:
        print(f"Update subtask failed and rolled back. Error: {e}")
        conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()
