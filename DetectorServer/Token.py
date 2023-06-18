import time

import jwt


class Token:  # 定义一个类
    def __init__(self, secret_key, algorithm='HS256'):  # 初始化方法，需要传入密钥和算法
        self.secret_key = secret_key  # 保存密钥
        self.algorithm = algorithm  # 保存算法

    def generate_token(self, payload):  # 定义一个生成token的方法，需要传入有效载荷
        payload['exp'] = int(time.time() + 3600 * 24 * 3)  # 在有效载荷中添加过期时间，这里设置为3天后
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)  # 使用pyjwt库的encode方法生成token
        return token  # 返回token

    def verify_token(self, token):  # 定义一个验证token的方法，需要传入token
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            # 使用pyjwt库的decode方法解码token,如果成功则返回有效载荷
            return payload  # 返回有效载荷
        except jwt.ExpiredSignatureError:  # 如果捕获到过期异常
            return None  # 返回None
        except jwt.InvalidTokenError:  # 如果捕获到其他无效异常
            return None  # 返回None
