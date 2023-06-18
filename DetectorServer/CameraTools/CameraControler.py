from concurrent.futures import ThreadPoolExecutor

from Camera import Camera


class CameraControler():

    def __init__(self):
        self.readPool = ThreadPoolExecutor(max_workers=100)
        self.writePool = ThreadPoolExecutor(max_workers=100)
        self.stacks = {}
        self.stack_size = 100

    def addCamera(self, cam):
        self.stacks[cam] = []
        cam = Camera(cam, self.stacks[cam], self.stack_size)
        cam.read_future = self.readPool.submit(cam.read)
        cam.write_future = self.writePool.submit(cam.write)

    def delCamera(self, cam):
        # ThreadPoolExecutor
        pass
