# -*- coding: utf-8 -*-
import sensor, image, time,sys
sys.path.append("openmv_project")
from config import (CAM_SETTINGS,COLOR_THRESHOLDS,ACU_DB,PERF_SETTINGS)
from vision import ArmAnalyzer
from comm import ProtocolHandler
from safety import SafetyMonitor

# ------------------ 初始化 ------------------
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.HQVGA)
sensor.set_vflip(CAM_SETTINGS['flip'])
sensor.set_hmirror(CAM_SETTINGS['mirror'])
sensor.skip_frames(2000)

# 模块初始化
analyzer = ArmAnalyzer()
comm = ProtocolHandler()
safety = SafetyMonitor()
clock = time.clock()

# ------------------ 主循环 ------------------
frame_counter = 0
while True:
    clock.tick()
    img = sensor.snapshot()

    # 性能优化：跳帧处理
    frame_counter = (frame_counter + 1) % PERF_SETTINGS['frame_skip']
    if frame_counter != 0:
        continue

    # 安全监测
    if not safety.check_motion(img):
        comm.send_alert("MOTION_ALERT")
        continue

    temp = safety.check_temperature()
    if temp > 60:
        comm.send_alert("OVERHEAT")
        break

    # 视觉分析
    anatomy = analyzer.detect_anatomy(img)
    if not anatomy:
        continue

    # 穴位定位与发送
    for acu_id in ACU_DB.keys():
        pos = analyzer.calculate_acu_point(anatomy, acu_id)
        if pos:
            x_mm = int(pos[0] * analyzer.cm_per_pixel * 10)
            y_mm = int(pos[1] * analyzer.cm_per_pixel * 10)
            comm.send_acu_data(acu_id, x_mm, y_mm, ACU_DB[acu_id]['pressure'])

            # 可视化
            img.draw_cross(pos[0], pos[1], color=(0,255,0))
            img.draw_string(pos[0], pos[1], acu_id)

    # 性能显示
    fps = clock.fps()
    img.draw_string(5,5, f"FPS:{fps:.1f} TEMP:{temp:.1f}C", color=(255,0,0))

    # 动态调整帧率
    if fps < PERF_SETTINGS['target_fps'] * 0.8:
        PERF_SETTINGS['frame_skip'] = max(1, PERF_SETTINGS['frame_skip'] -1)
    elif fps > PERF_SETTINGS['target_fps'] * 1.2:
        PERF_SETTINGS['frame_skip'] +=1
