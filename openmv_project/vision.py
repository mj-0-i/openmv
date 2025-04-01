# -*- coding: utf-8 -*-
import sensor, image, math, pyb
from config import *

class ArmAnalyzer:
    def __init__(self):
        self.cm_per_pixel = 0.05
        self.load_calibration()

    def load_calibration(self):
        try:
            with open('calibration.json', 'r') as f:
                calib = json.load(f)
                self.cm_per_pixel = calib['cm_per_pixel']
        except:
            print("Using default calibration")

    def detect_anatomy(self, img):
        # 预处理：高斯模糊降噪
        img.gaussian(1)
        
        # 自适应肤色检测（根据环境光调整阈值）
        thresholds = self._dynamic_skin_threshold(img)
        blobs = img.find_blobs(thresholds,
                             area_threshold=2000,
                             merge=True,
                             margin=10)
        
        if not blobs:
            return None
        
        # 选择最大连通域并过滤非手臂形状
        arm = max(blobs, key=lambda b: b.area())
        if arm.w / arm.h < 0.3 or arm.w / arm.h > 3:
            return None
        
        # 改进关键线检测：限制角度范围
        anatomy = {'contour': arm}
        elbow_roi = (arm.x, arm.y + arm.h // 4, arm.w, arm.h // 3)
        anatomy['elbow_line'] = self._find_dominant_line(img, elbow_roi, theta_range=(70, 110))
        
        wrist_roi = (arm.x, arm.y + 3 * arm.h // 4, arm.w, arm.h // 5)
        anatomy['wrist_line'] = self._find_dominant_line(img, wrist_roi, theta_range=(80, 100))
        
        return anatomy

    def _find_dominant_line(self, img, roi, theta_range):
        lines = img.find_lines(roi=roi,
                              theta_margin=25,
                              rho_margin=20,
                              threshold=1500,
                              theta_window=theta_range)
        return max(lines, key=lambda l: l.length()) if lines else None

    def _dynamic_skin_threshold(self, img):
        # 根据图像亮度动态调整阈值
        stats = img.get_statistics()
        l_adj = max(0, 50 - (stats.l_mean() - 80))
        return [(l_adj, 80, -20, 20, -20, 20)]
    
    def calculate_acu_point(self, anatomy, acu_id):
        acu_info = ACU_DB[acu_id]
        ref_point = self._get_ref_point(anatomy, acu_info['ref_point'])

        if not ref_point:
            return None

        # 三维坐标转换
        dx = int(acu_info['offset_cm'][0] / self.cm_per_pixel)
        dy = int(acu_info['offset_cm'][1] / self.cm_per_pixel)
        depth_comp = int(acu_info['depth_cm'] / self.cm_per_pixel * 0.3)

        return (ref_point[0] + dx + depth_comp,
                ref_point[1] + dy)

    def _get_ref_point(self, anatomy, ref_type):
        if ref_type == "elbow_line_end" and anatomy['elbow_line']:
            return anatomy['elbow_line'].end()
        elif ref_type == "wrist_line_mid" and anatomy['wrist_line']:
            return anatomy['wrist_line'].midpoint()
        elif ref_type == "wrist_line_ulnar" and anatomy['wrist_line']:
            return (anatomy['wrist_line'].x2(), anatomy['wrist_line'].y2())
        return None