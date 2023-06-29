import asyncio

from WeChat.WeChatServer import WeChatServer
from hypercorn.asyncio import serve
from hypercorn.config import Config

wechat_server = WeChatServer()
wechat_server_config = Config()
wechat_server_config.bind = ["127.0.0.1:8081"]

if __name__ == '__main__':

    asyncio.run(serve(wechat_server, wechat_server_config))
