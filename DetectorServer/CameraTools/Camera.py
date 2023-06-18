import gc
import os
import time

import cv2


class Camera():
    def __init__(self, cam, stack, stack_size):
        self.size = stack_size
        self.stack = stack
        self.cam = cam
        self.showImg = True

    def __del__(self):
        self.cap.release()

    # 向共享缓冲栈中写入数据:
    def write(self) -> None:

        print('Process to write: %s' % os.getpid())
        while True:
            _, img = self.cap.read()
            if _:
                self.stack.append(img)
                # print(stack)
                # 每到一定容量清空一次缓冲栈
                # 利用gc库，手动清理内存垃圾，防止内存溢出

                if len(self.stack) >= self.size:
                    del self.stack[:]
                    gc.collect()

    # 在缓冲栈中读取数据:
    def read(self) -> None:
        print('Process to read: %s' % os.getpid())
        # 开始时间
        t1 = time.time()
        # 图片计数
        count = 0

        while True:
            if len(self.stack) != 0:
                # 开始图片消耗
                print("stack的长度", len(self.stack))
                if len(self.stack) <= self.size and len(self.stack) != 0:
                    frame = self.stack.pop()
                else:
                    pass
                if len(self.stack) >= self.size:
                    del self.stack[:]
                    gc.collect()
                print("*" * 100)

                count += 1
                print("数量为：", count)

                t2 = time.time()
                print("时间差：", int(t2 - t1))

                if self.showImg:
                    cv2.imshow('MobilePose Demo', frame)
                    if cv2.waitKey(1) == 27:  # ESC
                        break
