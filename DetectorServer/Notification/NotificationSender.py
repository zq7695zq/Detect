from WeChat.WeChatNotification import WeChatNotification

class NotiSender:
    def __init__(self, db, user_id):
        self.db = db
        # 加载微信消息\绑定
        self.isWechatBound = False
        try:
            self.wechat = WeChatNotification()
            if self.db.user_is_bound(user_id):
                bound = {}
                if self.db.user_get_bound(user_id, bound):
                    self.open_id = bound['open_id']
                    self.isWechatBound = True
                    print('成功加载绑定WeChat：%s----%s' % (user_id, self.open_id))
        except:
            print("微信消息加载失败")
            self.isWechatBound = False

    def send(self, text):
        if self.isWechatBound:
            self.wechat.send(text, {'open_id': self.open_id})
