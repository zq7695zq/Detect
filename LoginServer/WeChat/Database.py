# 导入pymysql

from enum import Enum

import pymysql
from dbutils.pooled_db import PooledDB


class db_state(Enum):
    unk = 0
    error_user_is_exist = 1

    login_success = 2
    login_fail_user_is_not_exist = 3
    login_fail_password_wrong = 4

    user_info_success = 5
    user_info_fail_user_is_not_exist = 6
    user_info_unk_error = 7

    user_bind_success = 8
    user_bind_unk_error = 9

    def get_value(self):
        return str(self).replace('db_state.', '')


class mysql_db_wechat:

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
                # 查出当前查询的列名，保存到coloums
                coloums = [column[0] for column in cursor.description]
                for row in datas:
                    ret.update(dict(zip(coloums, row)))
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
            print("wechat_user_is_exist_by_username-数据库操作异常：\n", e)
        finally:
            cursor.close()
            conn.close()
            return is_exist

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
            print("wechat_user_login-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if len(datas) == 0:
                return db_state.login_fail_password_wrong
            else:
                return db_state.login_success

    def user_bind(self, user_id, openid):
        conn = self.pool.connection()
        try:
            with conn.cursor() as cursor:
                # 准备SQL语句
                sql = "insert into wechat values(null, %s, %s)"
                # 执行SQL语句
                cursor.execute(sql, [user_id, openid])
                # 提交事务
                conn.commit()
        except Exception as e:
            print("wechat_user_bind-数据库操作异常：\n", e)
        finally:
            # 不管成功还是失败，都要关闭数据库连接
            cursor.close()
            conn.close()
            if cursor.rowcount > 0:
                return db_state.user_bind_success
            else:
                return db_state.user_bind_unk_error
