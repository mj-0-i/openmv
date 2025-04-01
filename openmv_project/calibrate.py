import sensor, image, time, json, pyb
from pyb import UART
import os

# 初始化传感器
sensor.reset()
sensor.set_pixformat(sensor.RGB565)  # 颜色格式 RGB565
sensor.set_framesize(sensor.QVGA)  # 分辨率 320x240
sensor.skip_frames(time=2000)  # 等待摄像头稳定

# 初始化串口
uart = UART(3, 9600, timeout_char=1000)

# LED 反馈
led_green = pyb.LED(2)  # 绿灯
led_red = pyb.LED(1)  # 红灯

# 参考物体参数
REF_SIZE_CM = 5.0  # 参考卡片宽度（cm）
SAMPLES_NEEDED = 5  # 需要的采样次数

measurements = []  # 存储采样数据

print("等待串口输入 's' 进行采样（共 5 次完成校准）...")

def save_calibration():
    """删除旧的 JSON 文件，并保存新的校准数据"""
    avg_pixels = sum(measurements) / SAMPLES_NEEDED
    cm_per_pixel = REF_SIZE_CM / avg_pixels

    calibration_data = {
        "cm_per_pixel": round(cm_per_pixel, 5),
        "samples": measurements,
        "timestamp": time.localtime()
    }

    # 目标路径
    base_path = "openmv_project"
    file_path = base_path + "/calibration.json"

    # 确保目录存在
    try:
        os.listdir(base_path)  # 尝试列出目录内容以确认目录是否存在
    except OSError:
        os.mkdir(base_path)  # 如果目录不存在，则创建目录

    # **先删除旧的 JSON 文件**
    try:
        os.remove(file_path)
    except OSError:
        pass  # 文件不存在，无需删除

    # **写入新的 JSON 文件**
    tmp_file_path = file_path + ".tmp"  # 临时文件路径
    try:
        # 写入临时文件
        with open(tmp_file_path, "w") as f:
            f.write(json.dumps(calibration_data))
            f.flush()  # 确保数据写入磁盘
            os.sync()  # 同步文件系统

        # 重命名临时文件为目标文件
        os.rename(tmp_file_path, file_path)
        print(f"=== 校准完成 ===\n新校准文件已保存至: {file_path}")
        uart.write(f"Calibration Done. 1px = {cm_per_pixel:.5f} cm\n")
        print("JSON 文件已生成，可以结束运行")
    except Exception as e:
        print(f"Error writing file: {e}")
        uart.write(f"Error writing calibration file: {e}\n")
        # 删除可能残留的临时文件
        try:
            os.remove(tmp_file_path)
        except OSError:
            pass

        print(json.dumps(calibration_data, indent=4))


def process_frame():
    """拍摄、检测矩形，并在窗口中显示信息"""
    img = sensor.snapshot()
    rects = img.find_rects(threshold=2500)

    if rects:
        largest_rect = max(rects, key=lambda r: r.w() * r.h())
        img.draw_rectangle(largest_rect.rect(), color=(255, 0, 0))  # 画出检测框

        pixel_width = largest_rect.w()
        current_cmpp = REF_SIZE_CM / pixel_width

        # 在窗口中显示信息
        img.draw_string(10, 10, f"当前精度: {current_cmpp:.4f} cm/px", color=(0,255,0))
        img.draw_string(10, 30, f"已采集: {len(measurements)}/{SAMPLES_NEEDED}", color=(0,255,0))

        return pixel_width  # 返回当前检测的像素宽度
    else:
        img.draw_string(10, 10, "未检测到矩形", color=(255,0,0))  # 提示用户调整卡片位置
        return None

while True:
    pixel_width = process_frame()  # 实时更新摄像头画面

    if uart.any():  # 检测串口输入
        cmd = uart.readline()
        if cmd:
            cmd = cmd.decode().strip()
            print(f"收到命令: {cmd}")

            if cmd.lower() == 's':  # 触发采样
                if pixel_width:  # 确保检测到矩形
                    measurements.append(pixel_width)
                    print(f"[{len(measurements)}/{SAMPLES_NEEDED}] 采样成功！宽度: {pixel_width}px")

                    # 绿灯闪烁反馈
                    led_green.on()
                    time.sleep_ms(100)
                    led_green.off()

                    # 5 次采样后自动校准
                    if len(measurements) == SAMPLES_NEEDED:
                        save_calibration()
                        measurements = []  # 清空数据，支持下一轮采样
                else:
                    # 未检测到矩形，红灯闪烁提醒
                    led_red.on()
                    time.sleep_ms(100)
                    led_red.off()
                    print("未检测到矩形，采样无效！")

            else:
                print(f"未知命令: {cmd}")
                uart.write("Unknown Command\n")

    time.sleep_ms(50)  # 降低 CPU 负担
