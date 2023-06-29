import configparser

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from Database import db_state, mysql_db_detector
from PacketModels.Models import ModelLogin, ModelRegister, ModelAuthentication
from Token import Token

import hashlib

class LoginServer(FastAPI):

    def __init__(self, title: str = "Server"):
        super().__init__(title=title)

        config = configparser.ConfigParser()
        config.read('config.ini')

        self.db = mysql_db_detector(config)

        self.Token = Token(config.get("token", "secret_key"))

        self.media_mtx = dict(config.items("media_mtx"))

        print("加载loginserver成功")
        # self.detector_servers = []
        #
        # self.db.server_get_all(self.detector_servers)
        #
        # print("detector_servers:", self.detector_servers)

        @self.middleware("http")
        async def process_token(request: Request, call_next):
            if request.url.path.startswith("/login") or request.url.path.startswith("/register"):
                return await call_next(request)
            _token = request.headers.get("Authorization")
            if not _token:
                return JSONResponse(content={"detail": "Missing token"}, status_code=401)
            payload = self.Token.verify_token(_token)
            if not payload:
                return JSONResponse(content={"detail": "Invalid token"}, status_code=401)
            response = await call_next(request)
            return response

        @self.on_event("startup")
        async def on_startup():
            # 在这里执行应用程序启动时需要执行的操作
            pass

        @self.on_event("shutdown")
        async def on_shutdown():
            # 在这里执行应用程序关闭时需要执行的操作
            pass

        @self.post('/login')
        async def login(m: ModelLogin):
            state = self.db.user_login(m.username, m.password)
            ret = {'state': state.get_value()}
            if state == db_state.login_fail_password_wrong:
                pass
            elif state == db_state.error_user_is_exist:
                pass
            elif state == db_state.login_success:
                user_info = {}
                state_user_info = self.db.user_get_user(m.username, user_info)
                ret['token'] = self.Token.generate_token(
                    {'username': m.username, 'password': m.password, 'id': user_info['id']}
                )
                if state_user_info == db_state.user_info_unk_error:
                    ret['error'] = '未知错误'
                elif state_user_info == db_state.user_info_fail_user_is_not_exist:
                    pass
                else:
                    ret['user'] = {'email': user_info['email']}
                    server = {}
                    self.db.server_get_by_user_id(user_info['id'], server)
                    ret['server'] = server
            return ret

        @self.post('/register')
        async def register(m: ModelRegister):
            state = self.db.user_register(m.username, m.password, m.email)
            ret = {'state': state.get_value()}
            if state == db_state.register_error_unk:
                pass
            elif state == db_state.error_user_is_exist:
                pass
            elif state == db_state.register_success:
                # ret['token'] = self.Token.generate_token({'username': m.username, 'password': m.password})
                pass
            return ret

        @self.post('/rtsp_reader')
        async def rtsp_reader(m: ModelAuthentication):
            print(m)
            if m.user == self.media_mtx['readUser'] and m.password == self.media_mtx['readPass']:
                return {"status_code": status.HTTP_200_OK}
            return {"status_code": status.HTTP_}
