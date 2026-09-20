import unittest
import numpy as np
import cv2

from src.tracking.optical_tracker import OpticalTracker
from src.tracking.surgical_tool import SurgicalTool

class TestOpticalTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = OpticalTracker()

    def test_subpixel_extraction_synthetic_blob(self):
        """测试亚像素灰度加权质心提取算法"""
        img = np.zeros((100, 100), dtype=np.uint8)
        
        # 在真实物理坐标 (50.35, 40.65) 处生成一个高斯发光球斑点
        true_cx, true_cy = 50.35, 40.65
        for y in range(30, 52):
            for x in range(40, 62):
                dist_sq = (x - true_cx)**2 + (y - true_cy)**2
                val = 250 * np.exp(-dist_sq / 12.0)
                img[y, x] = np.clip(val, 0, 255).astype(np.uint8)

        centroids = self.tracker.extract_subpixel_markers(img, threshold_val=100)
        self.assertEqual(len(centroids), 1)
        
        detected_x, detected_y = centroids[0]
        # 亚像素质心误差应小于 0.05 像素
        self.assertAlmostEqual(detected_x, true_cx, delta=0.05)
        self.assertAlmostEqual(detected_y, true_cy, delta=0.05)

    def test_tool_loading(self):
        """测试器械定义加载与针尖模型解析"""
        self.assertEqual(len(self.tracker.tool.model_points), 4)
        np.testing.assert_allclose(self.tracker.tool.tool_tip_offset, [0.0, 150.0, -10.0])

if __name__ == '__main__':
    unittest.main()

