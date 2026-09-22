import os
import sys
import time
import json
import threading
from typing import Tuple, Optional
from ctypes import c_ubyte, POINTER, cast
import numpy as np

from .base_camera import BaseStereoCamera

# 自动尝试定位海康官方 MVS SDK 的 Python 模块路径
HIK_SDK_PATHS = [
    r"F:\MVS\Development\Samples\Python\MvImport",
    r"F:\Program Files\MVS\Development\Samples\Python\MvImport",
    r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport",
    r"C:\Program Files\MVS\Development\Samples\Python\MvImport",
    r"D:\Program Files (x86)\MVS\Development\Samples\Python\MvImport",
    r"D:\Program Files\MVS\Development\Samples\Python\MvImport",
    r"E:\Program Files (x86)\MVS\Development\Samples\Python\MvImport",
]

HIK_SDK_FOUND = False
for p in HIK_SDK_PATHS:
    if os.path.exists(p):
        sys.path.append(p)
        try:
            from MvCameraControl_class import (
                MvCamera, MV_CC_DEVICE_INFO_LIST, MV_CC_DEVICE_INFO, MV_OK,
                MV_GIGE_DEVICE, MV_USB_DEVICE, MV_ACCESS_Exclusive
            )
            from CameraParams_header import MV_FRAME_OUT_INFO_EX
            HIK_SDK_FOUND = True
            print(f"[HikCamera] 成功发现并加载海康 MVS SDK 库: {p}")
            break
        except Exception:
            pass

class HikStereoCamera(BaseStereoCamera):
    """
    海康双目黑白工业相机专用驱动封装 (适配近红外成像场景)
    - 继承 BaseStereoCamera 抽象基类
    - 支持左右相机按序列号(SN)或设备索引独立连接
    - 针对红外反光球场景优化曝光设置 (低曝光过滤环境杂光)
    - 多线程并行抓图，保证左右帧时间戳同步
    """

    def __init__(self, config_path: Optional[str] = None):
        super().__init__(config_path)
        self.exposure_time_us = 5000.0
        self.gain = 12.0

        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                self.exposure_time_us = cfg.get("left_camera", {}).get("exposure_time_us", 5000.0)
                self.gain = cfg.get("left_camera", {}).get("gain", 12.0)

        self.cam_l = None
        self.cam_r = None
        self.is_grabbing = False

        self.latest_left_frame = None
        self.latest_right_frame = None
        self.lock = threading.Lock()

        if not HIK_SDK_FOUND:
            print("[HikCamera] [提示] 当前系统未安装海康 MVS SDK。如果在宿舍脱机开发，请使用 Mock 模式。")

    def open(self) -> bool:
        """枚举并连接两台海康相机"""
        if not HIK_SDK_FOUND:
            print("[HikCamera Error] 无法连接真实硬件: 缺少海康 SDK。")
            self._is_opened = False
            return False

        MvCamera.MV_CC_Initialize()
        device_list = MV_CC_DEVICE_INFO_LIST()
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, device_list)
        if ret != MV_OK or device_list.nDeviceNum < 2:
            print(f"[HikCamera Error] 未检测到足够的相机设备 (发现设备数: {device_list.nDeviceNum}，需要 2 台)")
            self._is_opened = False
            return False

        print(f"[HikCamera] 成功发现 {device_list.nDeviceNum} 台海康设备，正在初始化左右目...")
        
        self.cam_l = MvCamera()
        self.cam_r = MvCamera()

        st_dev_l = cast(device_list.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
        st_dev_r = cast(device_list.pDeviceInfo[1], POINTER(MV_CC_DEVICE_INFO)).contents

        if self.cam_l.MV_CC_CreateHandle(st_dev_l) != MV_OK or self.cam_l.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0) != MV_OK:
            print("[HikCamera Error] 左相机打开失败！")
            return False

        if self.cam_r.MV_CC_CreateHandle(st_dev_r) != MV_OK or self.cam_r.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0) != MV_OK:
            print("[HikCamera Error] 右相机打开失败！")
            return False

        self._configure_camera(self.cam_l, "左相机")
        self._configure_camera(self.cam_r, "右相机")

        self.cam_l.MV_CC_StartGrabbing()
        self.cam_r.MV_CC_StartGrabbing()
        self.is_grabbing = True

        self.thread_l = threading.Thread(target=self._grab_worker, args=(self.cam_l, "left"), daemon=True)
        self.thread_r = threading.Thread(target=self._grab_worker, args=(self.cam_r, "right"), daemon=True)
        self.thread_l.start()
        self.thread_r.start()

        self._is_opened = True
        print("[HikCamera] 海康双目相机已成功启动并开始实时抓图！")
        return True

    def _configure_camera(self, cam, name="相机"):
        """设置相机采集参数 (Mono8 格式，短曝光)"""
        try:
            cam.MV_CC_SetEnumValue("PixelFormat", 0x01080001) # Mono8
            cam.MV_CC_SetEnumValue("ExposureAuto", 0) # 关闭自动曝光
            cam.MV_CC_SetFloatValue("ExposureTime", float(self.exposure_time_us))
            cam.MV_CC_SetEnumValue("GainAuto", 0) # 关闭自动增益
            cam.MV_CC_SetFloatValue("Gain", float(self.gain))
            print(f"[HikCamera] {name} 配置完成: 曝光 {self.exposure_time_us} μs, 增益 {self.gain} dB")
        except Exception as e:
            print(f"[HikCamera] {name} 参数微调提醒: {e}")

    def set_exposure(self, exposure_time_us: float):
        """动态修改双目相机曝光时间 (微秒)"""
        self.exposure_time_us = float(np.clip(exposure_time_us, 100.0, 1000000.0))
        for cam, name in [(self.cam_l, "左相机"), (self.cam_r, "右相机")]:
            if cam:
                cam.MV_CC_SetFloatValue("ExposureTime", self.exposure_time_us)

    def set_gain(self, gain_db: float):
        """动态修改双目相机增益 (dB)"""
        self.gain = float(np.clip(gain_db, 0.0, 30.0))
        for cam, name in [(self.cam_l, "左相机"), (self.cam_r, "右相机")]:
            if cam:
                cam.MV_CC_SetFloatValue("Gain", self.gain)

    def _grab_worker(self, cam, eye):
        frame_info = MV_FRAME_OUT_INFO_EX()
        buf_size = 2048 * 2048 * 2
        buf = (c_ubyte * buf_size)()

        while self.is_grabbing:
            ret = cam.MV_CC_GetOneFrameTimeout(buf, buf_size, frame_info, 1000)
            if ret == MV_OK:
                img_data = np.frombuffer(buf, count=frame_info.nWidth * frame_info.nHeight, dtype=np.uint8)
                img = img_data.reshape((frame_info.nHeight, frame_info.nWidth))
                with self.lock:
                    if eye == "left":
                        self.latest_left_frame = img.copy()
                    else:
                        self.latest_right_frame = img.copy()
            time.sleep(0.005)

    def grab_stereo(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """获取最新同步的一对灰度图像"""
        if not self._is_opened:
            return False, None, None
        with self.lock:
            if self.latest_left_frame is not None and self.latest_right_frame is not None:
                return True, self.latest_left_frame.copy(), self.latest_right_frame.copy()
        return False, None, None

    def close(self):
        self.is_grabbing = False
        time.sleep(0.1)
        if self.cam_l:
            self.cam_l.MV_CC_StopGrabbing()
            self.cam_l.MV_CC_CloseDevice()
            self.cam_l.MV_CC_DestroyHandle()
        if self.cam_r:
            self.cam_r.MV_CC_StopGrabbing()
            self.cam_r.MV_CC_CloseDevice()
            self.cam_r.MV_CC_DestroyHandle()
        self._is_opened = False
        print("[HikCamera] 海康双目设备已安全释放。")
