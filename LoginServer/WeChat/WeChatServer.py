import configparser
from enum import Enum

from fastapi import FastAPI, Depends
import hashlib

from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from WeChat.Database import mysql_db_wechat, db_state
from WeChat.WeChatMessage import parse_xml, Message


class UserState(Enum):
    binding_started = 1
    binding_inputted_user_name = 2
    binding_inputted_password = 3


class WeChatServer(FastAPI):

    def __init__(self, title: str = "Server"):
        super().__init__(title=title)

        self.wechat_token = 'EzmtOD04Mf5D5TdLwcjsih9th4uknjyT'

        config = configparser.ConfigParser()
        config.read('config.ini')

        self.db = mysql_db_wechat(config)

        self.user = {}

        print("加载wechatserver成功")

        @self.on_event("startup")
        async def on_startup():
            # 在这里执行应用程序启动时需要执行的操作
            pass

        @self.on_event("shutdown")
        async def on_shutdown():
            # 在这里执行应用程序关闭时需要执行的操作
            pass

        @self.get('/main')
        async def wx_main(signature: str, timestamp: str, nonce: str, echostr: str):
            """
            用来验证URL
            """
            sign = hashlib.sha1("".join(sorted([self.wechat_token, timestamp, nonce])).encode('UTF-8')).hexdigest()
            return HTMLResponse(content=echostr if sign == signature else "error")

        @self.post('/main')
        async def wx_main(request: Request, openid: str):
            """
            :param request: 此次网络请求
            :param openid: 发送消息的用户唯一Openid
            :return:
            """
            try:
                rec_msg = parse_xml(await request.body())
                to_user = rec_msg.FromUserName
                from_user = rec_msg.ToUserName
                print(rec_msg.FromUserName)
                if rec_msg.MsgType == 'text':
                    if rec_msg.Content == '绑定':
                        self.user[openid] = \
                            {
                                'state': UserState.binding_started,
                                'user_name': '',
                                'password': '',
                            }
                        return Response(
                            Message(to_user, from_user, content="绑定开启成功，请输入账号").send(),
                            media_type="application/xml")
                    elif self.user[openid]['state'] == UserState.binding_started:
                        self.user[openid]['user_name'] = rec_msg.Content
                        self.user[openid]['state'] = UserState.binding_inputted_user_name
                        return Response(
                            Message(to_user, from_user,
                                    content="成功输入账号名，请输入密码:%s" % rec_msg.Content).send(),
                            media_type="application/xml")
                    elif self.user[openid]['state'] == UserState.binding_inputted_user_name:
                        self.user[openid]['password'] = rec_msg.Content
                        self.user[openid]['state'] = None
                        state = self.db.user_login(self.user[openid]['user_name'],
                                                   hashlib.md5(
                                                       self.user[openid]['password'].encode(
                                                           encoding='utf-8')).hexdigest())
                        if state == db_state.login_success:
                            user_info = {}
                            state_user_info = self.db.user_get_user(self.user[openid]['user_name'], user_info)
                            if state_user_info == db_state.user_info_success:
                                if self.db.user_is_bound(user_info['id']):
                                    return Response(
                                        Message(to_user, from_user, content="该账号已经绑定过。").send(),
                                        media_type="application/xml")
                                else:
                                    state_bind = self.db.user_bind(user_info['id'], openid)
                                    if state_bind == db_state.user_bind_success:
                                        self.user.pop(openid)
                                        return Response(
                                            Message(to_user, from_user, content="绑定成功。").send(),
                                            media_type="application/xml")
                                    else:
                                        return Response(
                                            Message(to_user, from_user, content="绑定失败，未知错误。").send(),
                                            media_type="application/xml")
                        else:
                            return Response(
                                Message(to_user, from_user, content="绑定失败，账号或密码错误。").send(),
                                media_type="application/xml")
                    return Response(
                        Message(to_user, from_user, content='如果需要绑定账户，请回复绑定').send(),
                        media_type="application/xml")
                elif rec_msg.MsgType == 'event':
                    if rec_msg.Event == 'subscribe':
                        # todo 处理一下订阅消息
                        return Response(
                            Message(to_user, from_user, content='欢迎您的关注，回复绑定开启绑定账号流程').send(),
                            media_type="application/xml")
                    elif rec_msg.Event == 'unsubscribe':
                        # todo 处理一下取消订阅流程
                        pass
            except:
                return HTMLResponse('success')
