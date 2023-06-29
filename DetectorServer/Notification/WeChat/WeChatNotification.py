import json

import requests

from Notification import Notification


class WeChatNotification(Notification):
    def __init__(self):
        self.app_id = 'wxde897b449a83f099'
        self.app_secret = '20792307ae4607ab497f339d378092c2'
        self.access_token = self.get_access_token()
        self.template_id = 'L2kYAhgtABa_-p_BNHyMQR2rzE_6VfoVWMsI0AAorAU'

    def get_access_token(self):
        """
        获取access_token
        通过查阅微信公众号的开发说明就清晰明了了
        """
        url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={}&secret={}'. \
            format(self.app_id, self.app_secret)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36'
        }
        response = requests.get(url, headers=headers).json()
        access_token = response.get('access_token')
        return access_token

    def get_openid(self):
        """
        获取所有用户的openid
        微信公众号开发文档中可以查阅获取openid的方法
        """
        next_openid = ''
        url_openid = 'https://api.weixin.qq.com/cgi-bin/user/get?access_token=%s&next_openid=%s' % (
            self.access_token, next_openid)
        ans = requests.get(url_openid)
        open_ids = json.loads(ans.content)['data']['openid']
        return open_ids

    def send(self, mes: str, args: dict):
        """
        给所有用户发送消息
        模板地址：https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Template_Message_Interface.html
        """
        if 'open_id' not in args:
            print(type(self) + ': 错误参数')
            return
        open_id = args['open_id']
        url = "https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={}".format(self.access_token)
        body = {
            "touser": open_id,
            "template_id": self.template_id,
            # "url": "https://www.baidu.com/",
            "topcolor": "#FF0000",
            # 对应模板中的数据模板
            "data": {
                "mes": {
                    "value": mes,
                    "color": "#FF99CC"  # 文字颜色
                },
            }
        }
        data = bytes(json.dumps(body).encode('utf-8'))  # 将数据编码json并转换为bytes型
        response = requests.post(url, data=data)
        result = response.json()  # 将返回信息json解码
        if result['errcode'] == 0:
            return True
        else:
            print(result['errmsg'])
            return False
