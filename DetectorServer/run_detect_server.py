# ffmpeg -f dshow -i video="HP True Vision FHD CameraTools" -s 384*384 -r 24 -vcodec libx264 -rtbufsize 2048M  -preset:v ultrafast -tune:v zerolatency -rtsp_transport tcp -f rtsp rtsp://127.0.0.1:8554/camera_test
import asyncio
import json
import os

from fastapi.encoders import jsonable_encoder
from hypercorn.asyncio import serve
from hypercorn.config import Config

from DetectServer import DetectServer

# def show_images():
#
#     images = [redis.base64ToFrame(b) for b in redis.get_event_frames('2206d193-7020-432e-b172-972b17d0e70f')]
#     index = 0
#     while True:
#         cv2.imshow('img', images[index])
#         if index == 29:
#             index = 0
#         else:
#             index += 1
#         if cv2.waitKey(25) & 0xFF == ord('q'):
#             cv2.destroyAllWindows()
#             break
detect_server = DetectServer()
detect_server_config = Config()
detect_server_config.bind = ["localhost:8010"]
if __name__ == '__main__':
    # show_images()
    asyncio.run(serve(detect_server, detect_server_config))
    # cam_source = "rtsp://127.0.0.1:8554/camera_test"
    # detector = DetectorModel(cam_source, EventSaver(100, cam_source))
    # while True:
    #     detector.detect_frame()
    #     if not detector.is_available():
    #         break
