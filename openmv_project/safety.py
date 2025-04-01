# -*- coding: utf-8 -*-
import sensor, pyb

class SafetyMonitor:
    def __init__(self):
        self.prev_frame = None
        self.temp_sensor = pyb.ADC(pyb.Pin('P6'))
        self.alert = False

    def check_motion(self, current_frame):
        if self.prev_frame:
            diff = current_frame.sub(self.prev_frame).binary([(50, 255)])
            motion_level = diff.get_statistics().l_mean()
            if motion_level > 25:  # 运动超限阈值
                self.alert = True
        self.prev_frame = current_frame.copy()
        return not self.alert

    def check_temperature(self):
        temp = self.temp_sensor.read() * 3.3 / 4096 * 100  # 转换为℃
        if temp > 60:
            self.alert = True
        return temp

    def reset(self):
        self.alert = False
