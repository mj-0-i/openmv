# -*- coding: utf-8 -*-
import sensor, pyb

class SafetyMonitor:
    def __init__(self):
        self.prev_frame = None
        self.temp_sensor = pyb.ADC(pyb.Pin('P6'))
        self.alert = False
        self.alert_duration = 0  # 新增：记录警报持续时间

    def check_motion(self, current_frame):
        try:  # 新增：添加异常处理
            if self.prev_frame:
                # 创建副本以避免操作原始帧
                current_copy = current_frame.copy()
                prev_copy = self.prev_frame.copy()
                
                # 使用更稳健的方法计算差异
                diff = current_copy.difference(prev_copy)
                stats = diff.get_statistics()
                motion_level = stats.mean()[0]  # 使用平均值而不是l_mean
                
                # 调整阈值和添加去抖动
                if motion_level > 30:  # 稍微提高阈值
                    self.alert_duration += 1
                    if self.alert_duration >= 3:  # 需要连续3帧检测到运动
                        self.alert = True
                else:
                    # 逐渐减少警报持续时间，而不是立即重置
                    self.alert_duration = max(0, self.alert_duration - 1)
                    if self.alert_duration == 0:
                        self.alert = False
            
            # 缓存当前帧以供下次比较使用
            self.prev_frame = current_frame.copy()
            return not self.alert
            
        except Exception as e:
            print(f"Motion detection error: {e}")
            # 错误发生时，确保不会无限报警
            self.prev_frame = current_frame.copy()
            self.alert = False
            return True  # 默认返回安全

    def check_temperature(self):
        temp = self.temp_sensor.read() * 3.3 / 4096 * 100  # 转换为℃
        if temp > 60:
            self.alert = True
        return temp

    def reset(self):
        self.alert = False
        self.alert_duration = 0  # 新增：同时重置持续时间
        if self.prev_frame:
            self.prev_frame = None  # 清除之前的帧，强制重新开始比较