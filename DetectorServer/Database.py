# 导入pymysql
import time
from datetime import datetime
from enum import Enum

import pymysql
from dbutils.pooled_db import PooledDB


class db_state(Enum):
    unk = 0
    error_user_is_exist = 1

    login_success = 2
    login_fail_user_is_not_exist = 3
    login_fail_password_wrong = 4

    register_success = 5
    register_error_unk = 6

    user_info_success = 7
    user_info_fail_user_is_not_exist = 8
    user_info_unk_error = 9

    detector_cam_source_exist = 10

    detector_add_success = 11
    detector_add_error_unk = 12

    detector_get_success = 13
    detector_get_error_user_is_not_exist = 14
    detector_get_error_unk = 15

    server_get_success = 16

    reminder_add_success = 17
    reminder_add_error_unk = 18
    reminder_del_success = 19
    reminder_del_error_unk = 20

    def get_value(self):
        return str(self).replace('db_state.', '')


class mysql_db_detector():

    def __init__(self, config):
        # 创建连接池
        self.pool = PooledDB(
            creator=pymysql,  # 使用pymysql模块
            host=config.get('database', 'host'),
            port=int(config.get('database', 'port')),
            user=config.get('database', 'user'),
            passwd=config.get('database', 'passwd'),
            database=config.get('database', 'database'),
            charset=config.get('database', 'charset')
        )

    def __del__(self):
        self.pool.close()

    def detector_is_exist_by_cam_source(self, cam_source):
        is_exist = False
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "select * from detector where cam_source = %s"
                # 执行SQL语句
                cursor.execute(sql, [cam_source])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                is_exist = len(datas) > 0
        except Exception as e:
            print("detector_is_exist_by_cam_source-数据库操作异常：\n", e)
        finally:
            cursor.close()
            conn.close()
            return is_exist

    def detector_add(self, cam_source, nickname, owner, server_id, ret):
        if self.detector_is_exist_by_cam_source(cam_source):
            return db_state.detector_cam_source_exist
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "insert into detector values(null, %s, %s, %s)"
                # 执行SQL语句
                cursor.execute(sql, [cam_source, nickname, owner])
                # 提交事务
                conn.commit()
                detector_id = cursor.lastrowid
        except Exception as e:
            print("detector_add-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            try:
                with conn.cursor() as cursor:
                    # 准备SQL语句
                    sql = "insert into detector_server values(null, %s, %s)"
                    # 执行SQL语句
                    cursor.execute(sql, [detector_id, server_id])
                    # 提交事务
                    conn.commit()
            except Exception as e:
                print("detector_add-数据库操作异常：\n", e)
            finally:
                # 不管成功还是失败，都要关闭数据库连接
                cursor.close()
                conn.close()
                if cursor.rowcount > 0:
                    ret = {
                        'id': detector_id,
                        'cam_source': cam_source,
                        'nickname': nickname,
                        'owner': owner
                    }
                    return db_state.detector_add_success
                else:
                    return db_state.detector_add_error_unk

    def detector_get_all(self, ret):
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = """
                SELECT * FROM detector
                """
                # 执行SQL语句
                cursor.execute(sql)
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                # 查出当前查询的列名，保存到columns
                columns = [column[0] for column in cursor.description]
                for row in datas:
                    ret.append(dict(zip(columns, row)))
        except Exception as e:
            print("detector_get_all-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.detector_get_success
            else:
                return db_state.detector_get_success

    def detector_get_by_server(self, server_id, ret):
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = """
                SELECT * FROM detector
                    JOIN detector_server
                    ON detector.id = detector_server.detector_id
                    WHERE server_id = %s
                """
                # 执行SQL语句
                cursor.execute(sql, [server_id])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                # 查出当前查询的列名，保存到columns
                columns = [column[0] for column in cursor.description]
                for row in datas:
                    ret.append(dict(zip(columns, row)))
        except Exception as e:
            print("detector_get_by_server-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.detector_get_success
            else:
                return db_state.detector_get_success

    def detector_get_by_owner(self, owner, ret):
        if not self.user_is_exist_by_id(owner):
            return db_state.detector_get_error_user_is_not_exist
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = """
                SELECT * FROM detector
                WHERE owner = %s
                """
                # 执行SQL语句
                cursor.execute(sql, [owner])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                # 查出当前查询的列名，保存到columns
                columns = [column[0] for column in cursor.description]
                for row in datas:
                    ret.append(dict(zip(columns, row)))
        except Exception as e:
            print("detector_get_by_owner-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.detector_get_success
            else:
                return db_state.detector_get_success

    def user_is_exist_by_username(self, username):
        is_exist = False
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "select * from user where username = %s"
                # 执行SQL语句
                cursor.execute(sql, [username])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                is_exist = len(datas) > 0
        except Exception as e:
            print("user_is_exist_by_username-数据库操作异常：\n", e)
        finally:
            cursor.close()
            conn.close()
            return is_exist

    def user_is_exist_by_id(self, id):
        is_exist = False
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "select * from user where id = %s"
                # 执行SQL语句
                cursor.execute(sql, [id])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                is_exist = len(datas) > 0
        except Exception as e:
            print("user_is_exist_by_id-数据库操作异常：\n", e)
        finally:
            cursor.close()
            conn.close()
            return is_exist

    def user_register(self, username, password_hash, email):
        if self.user_is_exist_by_username(username):
            return db_state.error_user_is_exist
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "insert into user values(null, %s, %s, DEFAULT, %s)"
                # 执行SQL语句
                cursor.execute(sql, [username, password_hash, email])
                # 提交事务
                conn.commit()
                user_id = cursor.lastrowid
        except Exception as e:
            print("user_register-数据库操作异常：\n", e)
        finally:
            try:
                with conn.cursor() as cursor:
                    # 准备SQL语句
                    sql = """
                            INSERT INTO user_server (user_id, server_id) 
                                SELECT %s, id FROM servers ORDER BY RAND() LIMIT 1
                            """
                    # 执行SQL语句
                    cursor.execute(sql, [user_id])
                    # 提交事务
                    conn.commit()
            except Exception as e:
                print("user_register-数据库操作异常：\n", e)
            finally:
                # 不管成功还是失败，都要关闭数据库连接
                cursor.close()
                conn.close()
                if cursor.rowcount > 0:
                    return db_state.register_success
                else:
                    return db_state.register_error_unk

    def user_login(self, username, password_hash):
        if not self.user_is_exist_by_username(username):
            return db_state.login_fail_user_is_not_exist
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "select * from user where username = %s and password = %s"
                # 执行SQL语句
                cursor.execute(sql, [username, password_hash])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
        except Exception as e:
            print("user_login-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.login_fail_password_wrong
            else:
                return db_state.login_success

    def user_get_user(self, username, ret):
        if not self.user_is_exist_by_username(username):
            return db_state.user_info_fail_user_is_not_exist
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "select * from user where username = %s"
                # 执行SQL语句
                cursor.execute(sql, [username])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                # 查出当前查询的列名，保存到columns
                columns = [column[0] for column in cursor.description]
                for row in datas:
                    ret.update(dict(zip(columns, row)))
        except Exception as e:
            print("user_get_user-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.user_info_unk_error
            else:
                return db_state.user_info_success

    def user_is_owner_cam_source(self, cam_source, user_id):
        is_owner = False
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "select * from detector where cam_source = %s and owner = %s"
                # 执行SQL语句
                cursor.execute(sql, [cam_source, user_id])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                is_owner = len(datas) > 0
        except Exception as e:
            print("user_is_owner_cam_source-数据库操作异常：\n", e)
        finally:
            cursor.close()
            conn.close()
            return is_owner

    def server_get_by_user_id(self, user_id, ret):
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = """
                     SELECT * FROM servers WHERE servers.id = 
                        (SELECT server_id FROM user_server WHERE user_id = %s)
                     """
                # 执行SQL语句
                cursor.execute(sql, [user_id])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                # 查出当前查询的列名，保存到columns
                columns = [column[0] for column in cursor.description]
                for row in datas:
                    ret.update(dict(zip(columns, row)))
        except Exception as e:
            print("server_get_by_user_id-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.server_get_success
            else:
                return db_state.server_get_success

    def server_get_all(self, ret):
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = """
                     SELECT * FROM servers
                     """
                # 执行SQL语句
                cursor.execute(sql)
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                # 查出当前查询的列名，保存到columns
                columns = [column[0] for column in cursor.description]
                for row in datas:
                    ret.append(dict(zip(columns, row)))
        except Exception as e:
            print("detector_get_all-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.server_get_success
            else:
                return db_state.server_get_success

    def server_get_users_by_server_id(self, server_id, ret):
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = """
                        select * from user 
                            where 
                                id = (select user_id from user_server where server_id = %s)
                        """
                # 执行SQL语句
                cursor.execute(sql, [server_id])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                # 查出当前查询的列名，保存到columns
                columns = [column[0] for column in cursor.description]
                for row in datas:
                    ret.update(dict(zip(columns, row)))
        except Exception as e:
            print("server_get_users_by_server_id-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.user_info_unk_error
            else:
                return db_state.user_info_success

    def server_get_user_count(self, server_id):
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = """
                        select count(*) from user_server where server_id = %s
                        """
                # 执行SQL语句
                cursor.execute(sql, [server_id])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                count = cursor.fetchone()
        except Exception as e:
            print("server_get_user_count-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            return count

    def user_is_bound(self, user_id):
        is_bound = False
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "select * from wechat where user_id = %s"
                # 执行SQL语句
                cursor.execute(sql, [user_id])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                is_bound = len(datas) > 0
        except Exception as e:
            print("wechat_user_is_user_is_bound-数据库操作异常：\n", e)
        finally:
            cursor.close()
            conn.close()
            return is_bound

    def user_get_bound(self, user_id, ret):
        if not self.user_is_bound(user_id):
            return False
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = """
                SELECT * FROM wechat
                WHERE user_id = %s
                """
                # 执行SQL语句
                cursor.execute(sql, [user_id])
                # 执行完SQL语句后的返回结果都是保存在cursor中
                # 所以要从cursor中获取全部数据
                datas = cursor.fetchall()
                # 查出当前查询的列名，columns
                columns = [column[0] for column in cursor.description]
                for row in datas:
                    ret.update(dict(zip(columns, row)))
        except Exception as e:
            print("user_get_bound-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return False
            else:
                return True

    def reminder_add(self, reminder_name, cam_source, select_time, init_rect, user_id, reminder_type, last_frame):
        affected_rows = 0
        if not self.user_is_exist_by_id(user_id):
            return db_state.user_info_fail_user_is_not_exist
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "insert into reminder values(null, %s, %s, %s, %s, %s, %s, DEFAULT, %s)"
                # 执行SQL语句
                cursor.execute(sql,
                               [reminder_name, cam_source, select_time, init_rect, user_id, reminder_type, last_frame])
                # 提交事务
                conn.commit()
                affected_rows = cursor.rowcount
                reminder_id = cursor.lastrowid
        except Exception as e:
            print("reminder_add-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if affected_rows > 0:
                return {'state': db_state.reminder_add_success, 'reminder_id': reminder_id}
            else:
                return {'state': db_state.reminder_add_error_unk}

    def reminder_del(self, reminder_id):
        conn = self.pool.connection()
        affected_rows = 0
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "DELETE FROM reminder WHERE reminder_id = %s"
                # 执行SQL语句
                cursor.execute(sql, [reminder_id])
                # 提交事务
                conn.commit()
                affected_rows = cursor.rowcount
        except Exception as e:
            print("reminder_delete-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if affected_rows > 0:
                return db_state.reminder_del_success
            else:
                return db_state.reminder_del_error_unk

    def get_reminders_by_user_and_cam(self, user_id, cam_source, reminder_id=-1):
        conn = self.pool.connection()
        reminders = []

        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                if reminder_id == -1:
                    sql = "SELECT * FROM reminder WHERE user_id = %s AND cam_source = %s"
                    # 执行SQL语句
                    cursor.execute(sql, [user_id, cam_source])
                else:
                    sql = "SELECT * FROM reminder WHERE user_id = %s AND cam_source = %s AND id = %s"
                    # 执行SQL语句
                    cursor.execute(sql, [user_id, cam_source, reminder_id])
                # 获取查询结果
                results = cursor.fetchall()

                for row in results:
                    reminder_id, reminder_name, cam_source, select_time_str \
                        , init_rect_str, user_id, reminder_type, start_time, last_frame = row
                    # Create a reminder dictionary and add it to the list
                    reminder = {
                        'id': reminder_id,
                        'reminder_name': reminder_name,
                        'cam_source': cam_source,
                        'select_time_str': select_time_str,
                        'init_rect_str': init_rect_str,
                        'user_id': user_id,
                        'reminder_type': reminder_type,
                        'start_time': start_time.timestamp(),
                        'last_frame': last_frame
                    }

                    reminders.append(reminder)
        except Exception as e:
            print("get_reminders_by_user_and_cam - 数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()

        return reminders

    def reminder_update_start_time(self, reminder_id):
        conn = self.pool.connection()
        # 打开数据库可能会有风险，所以添加异常捕捉
        try:
            with conn.cursor() as cursor:
                sql = "UPDATE reminder SET start_time = DEFAULT WHERE id = %s"
                cursor.execute(sql, [reminder_id])
                conn.commit()
        except Exception as e:
            print("reminder_update_start_time-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()