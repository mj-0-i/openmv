# environment.py
import sensor

class EnvAdapter:
    def __init__(self):
        self.auto_mode = True

    def adjust_exposure(self, img):
        if not self.auto_mode:
            return
        stats = img.get_statistics()
        target = 100  # 目标亮度值
        sensor.set_auto_exposure(True)
        if stats.l_mean() < target - 20:
            sensor.set_auto_gain(True)
        else:
            sensor.set_auto_gain(False)

# 在main.py中初始化并使用
