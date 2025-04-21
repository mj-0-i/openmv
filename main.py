# -*- coding: utf-8 -*-
import sensor, image, time, sys
sys.path.append("openmv_project")
import config, vision, comm, safety, environment
from config import *
from vision import ArmAnalyzer
from comm import ProtocolHandler
from safety import SafetyMonitor
from environment import EnvAdapter

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
env_adapter = EnvAdapter()

# 定义初始ROI
roi = (80, 40, 160, 120)  # 仅处理图像中心区域

# ------------------ 主循环 ------------------
frame_counter = 0
motion_alert_counter = 0  # 添加这一行，定义motion_alert_counter变量
while True:
    clock.tick()
    img = sensor.snapshot()
    env_adapter.adjust_exposure(img)  # 新增行

    # 性能优化：跳帧处理
    frame_counter = (frame_counter + 1) % PERF_SETTINGS['frame_skip']
    if frame_counter != 0:
        continue

      # 安全监测
    try:  # 新增：添加异常处理
       is_safe = safety.check_motion(img)
       if not is_safe:
           print("MOTION_ALERT detected!")  # 替代方案，而不是comm.send_alert
           motion_alert_counter += 1
           if motion_alert_counter > 5:  # 如果连续5帧都检测到运动，重置安全监视器
               safety.reset()
               motion_alert_counter = 0
           continue
       else:
           motion_alert_counter = 0  # 如果安全，重置计数器
    except Exception as e:
       print(f"Error in motion detection: {e}")
       safety.reset()  # 出现异常时重置安全监视器
       continue


    # 视觉分析
    print("Calling detect_anatomy with img:", img)
    anatomy = analyzer.detect_anatomy(img)
    print(f"Anatomy detection result: {anatomy}")
    if not anatomy:
        continue

    # 动态调整ROI基于手臂位置
    if 'contour' in anatomy:
        contour = anatomy['contour']
        roi = (
            max(0, contour.x() - 20),
            max(0, contour.y() - 20),
            min(contour.w() + 40, 240),
            min(contour.h() + 40, 160)
        )

     # 确保ACU_DB被正确导入
    if 'ACU_DB' not in globals():
       print("错误: ACU_DB未定义，尝试重新导入")
       from config import ACU_DB

       # 穴位定位与发送
    print(f"可用穴位: {list(ACU_DB.keys())}")  # 调试输出
    for acu_id in ACU_DB.keys():
        pos = analyzer.calculate_acu_point(anatomy, acu_id)
        if pos:
            x_mm = int(pos[0] * analyzer.cm_per_pixel * 10)
            y_mm = int(pos[1] * analyzer.cm_per_pixel * 10)
            comm.send_acu_data(acu_id, x_mm, y_mm, ACU_DB[acu_id]['pressure'])

            # 可视化
            img.draw_cross(pos[0], pos[1], color=(0, 255, 0),size=5)
            img.draw_string(pos[0], pos[1], f"{acu_id}: {ACU_DB[acu_id]['name']}")

    # 性能显示
    fps = clock.fps()
    img.draw_string(5, 5, f"FPS:{fps:.1f} ", color=(255, 0, 0))

    # 动态调整帧率
    if fps < PERF_SETTINGS['target_fps'] * 0.8:
        PERF_SETTINGS['frame_skip'] = max(1, PERF_SETTINGS['frame_skip'] - 1)
    elif fps > PERF_SETTINGS['target_fps'] * 1.2:
        PERF_SETTINGS['frame_skip'] += 1
