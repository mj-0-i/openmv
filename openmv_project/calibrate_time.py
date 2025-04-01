{"timestamp": [2015, 1, 1, 0, 6, 32, 3, 1], "samples": [128, 101, 232, 51, 51], "cm_per_pixel": 0.0444}                                                                                                                                                                                                                                                                                                                                                                                                                         )  # 红色文字提示
BOX_COLOR = (0, 255, 0)   # 绿色方框

def run_calibration():
    measurements = []
    led = pyb.LED(1)      # 使用红色LED作为状态指示
    start_time = time.ticks_ms()  # 记录开始时间

    # 初始倒计时提示
    for i in range(INIT_DELAY, 0, -1):
        img = sensor.snapshot()
        img.draw_string(10, 10, f"准备倒计时: {i}秒", color=TEXT_COLOR)
        img.draw_string(10, 30, "请放置校准卡片!", color=TEXT_COLOR)
        time.sleep(1)

    # 开始自动采样
    sample_count = 0
    while sample_count < SAMPLES_NEEDED:
        img = sensor.snapshot()

        # 实时检测卡片
        rects = img.find_rects(threshold=2500)
        found = False

        if rects:
            largest_rect = max(rects, key=lambda r: r.w() * r.h())
            if largest_rect.w() > 50:  # 过滤小面积误检
                found = True
                img.draw_rectangle(largest_rect.rect(), color=BOX_COLOR)
                pixel_width = largest_rect.w()

                # 显示状态信息
                img.draw_string(10, 10, f"采样进度: {sample_count+1}/{SAMPLES_NEEDED}", color=TEXT_COLOR)
                img.draw_string(10, 30, f"当前宽度: {pixel_width}px", color=TEXT_COLOR)
                img.draw_string(10, 50, "请勿移动卡片!", color=TEXT_COLOR)

                # 到达采样间隔时记录数据
                if time.ticks_diff(time.ticks_ms(), start_time) >= INTERVAL*1000:
                    measurements.append(pixel_width)
                    sample_count += 1
                    start_time = time.ticks_ms()  # 重置计时器

                    # LED反馈
                    led.on()
                    time.sleep_ms(100)
                    led.off()

        # 未找到卡片提示
        if not found:
            img.draw_string(10, 10, "未检测到校准卡片!", color=TEXT_COLOR)
            img.draw_string(10, 30, "请放置5cm白色卡片", color=TEXT_COLOR)

        time.sleep_ms(100)  # 降低CPU占用

    # 计算并保存校准参数
    avg_width = sum(measurements) / SAMPLES_NEEDED
    cm_per_pixel = REF_SIZE_CM / avg_width

    calibration_data = {
        "cm_per_pixel": round(cm_per_pixel, 5),
        "samples": measurements,
        "timestamp": list(time.localtime())  # 转换为可序列化格式
    }

    json_data = json.dumps(calibration_data)  # 转换为格式化 JSON
    print("即将写入 JSON 数据:\n", json_data)  # 先打印出来
    with open("calibration.json", "w") as f:
      f.write(json_data)  # 确保写入的是 JSON 数据
      f.flush()
      os.sync()

    # 在终端打印 JSON 数据
    print("校准结果 JSON 数据:\n", json_data)  # 直接打印 JSON 数据

    # 完成提示
    for _ in range(3):
        led.on()
        time.sleep_ms(300)
        led.off()
        time.sleep_ms(300)
    print("校准完成! 结果已保存")

run_calibration()
