# -*- coding: utf-8 -*-
# 系统配置参数

# 摄像头参数
CAM_SETTINGS = {
    'resolution': (240, 160),  # HQVGA
    'flip': True,
    'mirror': True
}

# 颜色阈值（YCrCb空间）
COLOR_THRESHOLDS = {
    'skin': [(50, 80, -20, 20, -20, 20)],  # 肤色
    'calibration': [(0, 100, -128, 127, -128, 127)]  # 校准卡片
}

# 穴位数据库
ACU_DB = {
    "LI11": {
        "name": "曲池",
        "ref_point": "elbow_line_end",
        "offset_cm": (0.5, 0),
        "depth_cm": 1.2,
        "pressure": 80
    },
    "PC3": {
        "name": "曲泽",
        "ref_point": "wrist_line_mid",
        "offset_cm": (2.0, 0.5),
        "depth_cm": 0.8,
        "pressure": 70
    },
    "HT7": {
        "name": "神门",
        "ref_point": "wrist_line_ulnar",
        "offset_cm": (0.0, -1.0),
        "depth_cm": 0.5,
        "pressure": 60
    }
}

# 性能参数
PERF_SETTINGS = {
    'target_fps': 15,
    'frame_skip': 2
}
