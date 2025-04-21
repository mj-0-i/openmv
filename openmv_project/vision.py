# -*- coding: utf-8 -*-
import sensor, image, math, pyb
from config import *
import ml, uos, gc
from ulab import numpy as np
import json  # 确保导入json模块

class ArmAnalyzer:
    def __init__(self):
        self.cm_per_pixel = 0.05
        self.load_calibration()
        # 加载Edge Impulse模型
        self.net = None
        self.labels = None
        self.load_ei_model()
        
        # 定义穴位在手臂上的相对位置（比例）
        self.acupoint_relative_positions = {
            "LI11": 0.15,  # 肘关节附近，距离肘部约15%的手臂长度
            "PC3": 0.25,   # 肘窝区域，距离肘部约25%的手臂长度
            "HT7": 0.9,    # 腕关节附近，距离肘部约90%的手臂长度
        }
        
        # 内部穴位数据库，用于在config导入失败时的备选方案
        self.internal_acu_db = {
            "LI11": {
                "name": "曲池",
                "offset_cm": (0.5, 0),
                "depth_cm": 1.2,
                "pressure": 80
            },
            "PC3": {
                "name": "曲泽",
                "offset_cm": (0.5, 0.5),
                "depth_cm": 0.8,
                "pressure": 70
            },
            "HT7": {
                "name": "神门",
                "offset_cm": (0.0, -1.0),
                "depth_cm": 0.5,
                "pressure": 60
            }
        }

    def load_calibration(self):
        try:
            with open('calibration.json', 'r') as f:
                calib = json.load(f)
                self.cm_per_pixel = calib['cm_per_pixel']
        except Exception as e:
            print(f"Using default calibration: {e}")

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
                
                # 添加输出每个标签的置信度
                print("AI 预测结果:")
                for label, confidence in predictions_list:
                    print(f"{label}: {confidence:.3f}")
                
                # 找出置信度最高的预测结果
                best_prediction = max(predictions_list, key=lambda x: x[1])
                
                # 如果是"arm"类别且置信度超过阈值
                if ("arm" in best_prediction[0].lower() or "手臂" in best_prediction[0]) and best_prediction[1] > 0.6:
                    arm_detected = True
                    # 在图像上标记识别结果
                    img.draw_string(5, 5, f"{best_prediction[0]}: {best_prediction[1]:.2f}", color=(0, 255, 0))
                    
                print(f"手臂识别状态: {arm_detected}")
                
            except Exception as e:
                print(f"Error during AI inference: {e}")
        
        # 创建解剖结构字典
        anatomy = {}
        
        if arm_detected:
            # 使用边缘检测来确定手臂方向
            edges = img.copy()
            edges.gaussian(1)
            edges.find_edges(image.EDGE_CANNY, threshold=(50, 150))
            
            # 寻找最长的线作为手臂方向的指示
            try:
                lines = edges.find_lines(threshold=1000, theta_margin=40, rho_margin=40)
                
                if lines and len(lines) > 0:
                    # 找出最长的线
                    longest_line = max(lines, key=lambda l: l.length())
                    
                    # 确定线的方向
                    is_vertical = abs(longest_line.y2() - longest_line.y1()) > abs(longest_line.x2() - longest_line.x1())
                    
                    # 设置手臂的端点
                    # 确保近端点是上方/左侧点，远端点是下方/右侧点
                    if (is_vertical and longest_line.y1() > longest_line.y2()) or (not is_vertical and longest_line.x1() > longest_line.x2()):
                        proximal_point = (longest_line.x2(), longest_line.y2())
                        distal_point = (longest_line.x1(), longest_line.y1())
                    else:
                        proximal_point = (longest_line.x1(), longest_line.y1())
                        distal_point = (longest_line.x2(), longest_line.y2())
                    
                    # 计算手臂长度
                    arm_length = math.sqrt((distal_point[0] - proximal_point[0])**2 + 
                                         (distal_point[1] - proximal_point[1])**2)
                    
                    # 在图像上绘制检测到的手臂线条
                    img.draw_line(proximal_point[0], proximal_point[1], 
                                distal_point[0], distal_point[1], color=(0, 255, 0), thickness=2)
                    
                    anatomy['proximal_point'] = proximal_point
                    anatomy['distal_point'] = distal_point
                    anatomy['is_vertical'] = is_vertical
                    anatomy['arm_length'] = arm_length
                    
                    # 创建一个模拟的contour对象，用于向后兼容
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
                    
                    # 计算包围手臂的矩形区域
                    min_x = min(proximal_point[0], distal_point[0])
                    min_y = min(proximal_point[1], distal_point[1])
                    width = abs(distal_point[0] - proximal_point[0])
                    height = abs(distal_point[1] - proximal_point[1])
                    
                    # 确保尺寸合理，至少有10像素的宽度和高度
                    width = max(10, width)
                    height = max(10, height)
                    
                    anatomy['contour'] = ArmContour(min_x, min_y, width, height)
                else:
                    # 如果没有检测到线条，则使用图像中心区域作为默认的手臂位置
                    img_width = img.width()
                    img_height = img.height()
                    
                    # 默认假设手臂是垂直的
                    center_x = img_width // 2
                    center_y = img_height // 4
                    
                    proximal_point = (center_x, center_y)
                    distal_point = (center_x, center_y + img_height // 2)
                    is_vertical = True
                    arm_length = img_height // 2
                    
                    # 在图像上绘制默认的手臂线条
                    img.draw_line(proximal_point[0], proximal_point[1], 
                               distal_point[0], distal_point[1], color=(255, 0, 0), thickness=2)
                    
                    anatomy['proximal_point'] = proximal_point
                    anatomy['distal_point'] = distal_point
                    anatomy['is_vertical'] = is_vertical
                    anatomy['arm_length'] = arm_length
                    
                    # 创建模拟的contour
                    anatomy['contour'] = ArmContour(center_x - 20, center_y, 40, arm_length)
            except Exception as e:
                print(f"Error detecting arm direction: {e}")
                # 使用默认的垂直手臂位置
                img_width = img.width()
                img_height = img.height()
                
                center_x = img_width // 2
                center_y = img_height // 4
                
                proximal_point = (center_x, center_y)
                distal_point = (center_x, center_y + img_height // 2)
                is_vertical = True
                arm_length = img_height // 2
                
                anatomy['proximal_point'] = proximal_point
                anatomy['distal_point'] = distal_point
                anatomy['is_vertical'] = is_vertical
                anatomy['arm_length'] = arm_length
                anatomy['contour'] = ArmContour(center_x - 20, center_y, 40, arm_length)
        else:
            # 使用传统方法进行手臂检测
            img.gaussian(1)
            
            # 自适应肤色检测
            thresholds = self._dynamic_skin_threshold(img)
            blobs = img.find_blobs(thresholds,
                                 area_threshold=2000,
                                 merge=True,
                                 margin=10)
            
            if not blobs:
                return None
            
            # 选择最大连通域并过滤非手臂形状
            arm = max(blobs, key=lambda b: b.area())
            if arm.w() / arm.h() < 0.3 or arm.w() / arm.h() > 3:
                return None
            
            # 确定手臂方向
            is_vertical = arm.h() > arm.w()
            
            # 确定手臂的端点
            if is_vertical:
                proximal_point = (arm.cx(), arm.y())
                distal_point = (arm.cx(), arm.y() + arm.h())
                arm_length = arm.h()
            else:
                proximal_point = (arm.x(), arm.cy())
                distal_point = (arm.x() + arm.w(), arm.cy())
                arm_length = arm.w()
            
            # 在图像上绘制检测到的手臂轮廓
            img.draw_rectangle(arm.rect(), color=(255, 0, 0))
            img.draw_line(proximal_point[0], proximal_point[1], 
                       distal_point[0], distal_point[1], color=(0, 255, 0), thickness=2)
            
            anatomy['proximal_point'] = proximal_point
            anatomy['distal_point'] = distal_point
            anatomy['is_vertical'] = is_vertical
            anatomy['arm_length'] = arm_length
            anatomy['contour'] = arm
            
        # 在图像上标记近端点和远端点
        img.draw_cross(anatomy['proximal_point'][0], anatomy['proximal_point'][1], color=(255, 0, 0), size=10)
        img.draw_cross(anatomy['distal_point'][0], anatomy['distal_point'][1], color=(0, 0, 255), size=10)
        
        print(f"手臂检测结果: 近端点={anatomy['proximal_point']}, 远端点={anatomy['distal_point']}, 长度={anatomy['arm_length']}")
        
        return anatomy

    def _dynamic_skin_threshold(self, img):
        # 根据图像亮度动态调整阈值
        stats = img.get_statistics()
        l_adj = max(0, 50 - (stats.l_mean() - 80))
        return [(l_adj, 80, -20, 20, -20, 20)]
    
    def calculate_acu_point(self, anatomy, acu_id):
        """根据手臂长度比例计算穴位位置"""
        if 'proximal_point' not in anatomy or 'distal_point' not in anatomy:
            print(f"计算穴位 {acu_id} 失败: 缺少手臂端点信息")
            return None
            
        try:
            # 获取穴位在手臂上的相对位置（从近端到远端的比例）
            relative_pos = self.acupoint_relative_positions.get(acu_id, 0.5)  # 默认在手臂中部
            
            # 获取手臂的近端点和远端点
            proximal_x, proximal_y = anatomy['proximal_point']
            distal_x, distal_y = anatomy['distal_point']
            
            # 计算穴位在手臂上的位置（线性插值）
            point_x = int(proximal_x + relative_pos * (distal_x - proximal_x))
            point_y = int(proximal_y + relative_pos * (distal_y - proximal_y))
            
            # 尝试从全局ACU_DB获取穴位信息
            try:
                acu_info = ACU_DB[acu_id]
            except (NameError, KeyError):
                # 使用内部数据库作为备选
                acu_info = self.internal_acu_db[acu_id]
            
            # 计算手臂的方向向量
            arm_dx = distal_x - proximal_x
            arm_dy = distal_y - proximal_y
            arm_length = math.sqrt(arm_dx**2 + arm_dy**2)
            
            # 处理手臂长度为0的特殊情况
            if arm_length < 1:
                return (point_x, point_y)
            
            # 归一化手臂方向向量
            arm_dx /= arm_length
            arm_dy /= arm_length
            
            # 计算垂直于手臂的方向向量（法向量）
            perp_dx = -arm_dy
            perp_dy = arm_dx
            
            # 获取偏移值
            offset_x = float(acu_info['offset_cm'][0]) / self.cm_per_pixel
            offset_y = float(acu_info['offset_cm'][1]) / self.cm_per_pixel
            
            # 应用偏移（垂直于手臂方向和沿着手臂方向的组合）
            dx = int(perp_dx * offset_x)
            dy = int(perp_dy * offset_x)
            
            # 深度补偿（通常应用在手臂法向量方向）
            depth_comp = float(acu_info['depth_cm']) / self.cm_per_pixel * 0.1
            dx += int(perp_dx * depth_comp)
            dy += int(perp_dy * depth_comp)
            
            # 最终穴位位置
            final_x = point_x + dx
            final_y = point_y + dy
            
            print(f"穴位 {acu_id} ({acu_info['name']}) 计算位置: ({final_x}, {final_y}), 相对位置: {relative_pos}")
            return (final_x, final_y)
            
        except (ValueError, TypeError) as e:
            print(f"计算穴位 {acu_id} 时出错: {e}")
            return None