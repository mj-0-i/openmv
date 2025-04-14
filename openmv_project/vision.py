# -*- coding: utf-8 -*-
import sensor, image, math, pyb
from config import *
import ml, uos, gc
from ulab import numpy as np

class ArmAnalyzer:
    def __init__(self):
        self.cm_per_pixel = 0.05
        self.load_calibration()
        # 加载Edge Impulse模型
        self.net = None
        self.labels = None
        self.load_ei_model()

    def load_calibration(self):
        try:
            with open('calibration.json', 'r') as f:
                calib = json.load(f)
                self.cm_per_pixel = calib['cm_per_pixel']
        except:
            print("Using default calibration")

    def load_ei_model(self):
        # 尝试加载Edge Impulse模型和标签
        try:
            # 如果可用内存足够，加载模型到堆上，否则加载到FB
            self.net = ml.Model("trained.tflite", load_to_fb=uos.stat('trained.tflite')[6] > (gc.mem_free() - (64*1024)))
            self.labels = [line.rstrip('\n') for line in open("labels.txt")]
            print("Edge Impulse model loaded successfully")
        except Exception as e:
            print(f"Could not load Edge Impulse model: {e}")
            print("Falling back to traditional vision methods")

    def detect_anatomy(self, img):
        # 首先尝试使用AI模型识别手臂
        arm_detected = False
        if self.net and self.labels:
            try:
                # 使用Edge Impulse模型预测
                predictions = self.net.predict([img])[0].flatten().tolist()
                predictions_list = list(zip(self.labels, predictions))
                
                # 找出置信度最高的预测结果
                best_prediction = max(predictions_list, key=lambda x: x[1])
                
                # 如果是"arm"类别且置信度超过阈值
                if ("arm" in best_prediction[0].lower() or "手臂" in best_prediction[0]) and best_prediction[1] > 0.6:
                    arm_detected = True
                    # 在图像上标记识别结果
                    img.draw_string(5, 5, f"{best_prediction[0]}: {best_prediction[1]:.2f}", color=(0, 255, 0))
            except Exception as e:
                print(f"Error during AI inference: {e}")
        
        # 如果AI没有检测到手臂或未加载AI模型，使用传统方法进行检测
        if not arm_detected:
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
        else:
            # 如果AI检测到手臂，创建基于整个图像的轮廓
            # 注：这里需要根据实际情况进行调整
            img_width = img.width()
            img_height = img.height()
            
            # 创建一个覆盖整个图像的contour来模拟检测到的手臂区域
            class ArmContour:
                def __init__(self, x, y, w, h):
                    self._x = x
                    self._y = y
                    self._w = w
                    self._h = h
                    
                def x(self): return self._x
                def y(self): return self._y
                def w(self): return self._w
                def h(self): return self._h
                def area(self): return self._w * self._h
                
            # 使用图像中心区域
            center_x = img_width // 4
            center_y = img_height // 4
            center_w = img_width // 2
            center_h = img_height // 2
            arm = ArmContour(center_x, center_y, center_w, center_h)
            
            anatomy = {'contour': arm}
            elbow_roi = (arm.x(), arm.y() + arm.h() // 4, arm.w(), arm.h() // 3)
            anatomy['elbow_line'] = self._find_dominant_line(img, elbow_roi, theta_range=(70, 110))
            
            wrist_roi = (arm.x(), arm.y() + 3 * arm.h() // 4, arm.w(), arm.h() // 5)
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
        
         # 打印 offset_cm 和 depth_cm 的值及类型
        print(f"offset_cm: {acu_info['offset_cm']}, type: {type(acu_info['offset_cm'])}")
        print(f"depth_cm: {acu_info['depth_cm']}, type: {type(acu_info['depth_cm'])}")

        try:
           offset_cm_0 = float(acu_info['offset_cm'][0])  # 强制转换为浮动类型
           offset_cm_1 = float(acu_info['offset_cm'][1])  # 强制转换为浮动类型
           depth_cm = float(acu_info['depth_cm'])  # 强制转换为浮动类型

           dx = int(offset_cm_0 / self.cm_per_pixel)
           dy = int(offset_cm_1 / self.cm_per_pixel)
           depth_comp = int(depth_cm / self.cm_per_pixel * 0.3)
        except (ValueError, TypeError) as e:
           print(f"Error in converting values: {e}")
           return None

        return (ref_point[0] + dx + depth_comp,
                ref_point[1] + dy)


    def _get_ref_point(self, anatomy, ref_type):
      if ref_type == "elbow_line_end" and anatomy['elbow_line']:
        # 手动获取线条的终点坐标
        elbow_line = anatomy['elbow_line']
        return (elbow_line.x2(), elbow_line.y2())  # 获取线条的第二个端点
      elif ref_type == "wrist_line_mid" and anatomy['wrist_line']:
        # 手动计算手腕线的中点
        wrist_line = anatomy['wrist_line']
        midpoint_x = (wrist_line.x1() + wrist_line.x2()) // 2
        midpoint_y = (wrist_line.y1() + wrist_line.y2()) // 2
        return (midpoint_x, midpoint_y)
      elif ref_type == "wrist_line_ulnar" and anatomy['wrist_line']:
        return (anatomy['wrist_line'].x2(), anatomy['wrist_line'].y2())
      return None
