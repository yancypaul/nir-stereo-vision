import unittest
import numpy as np
import cv2

from src.tracking.rigid_registration import register_point_sets_svd, match_rigid_body_correspondence

def euler_to_matrix(rx_deg, ry_deg, rz_deg):
    """纯 NumPy 实现欧拉角转 3x3 旋转矩阵 (无需依赖 scipy)"""
    rx = np.radians(rx_deg)
    ry = np.radians(ry_deg)
    rz = np.radians(rz_deg)

    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(rx), -np.sin(rx)],
        [0, np.sin(rx),  np.cos(rx)]
    ])
    Ry = np.array([
        [ np.cos(ry), 0, np.sin(ry)],
        [ 0,          1, 0         ],
        [-np.sin(ry), 0, np.cos(ry)]
    ])
    Rz = np.array([
        [np.cos(rz), -np.sin(rz), 0],
        [np.sin(rz),  np.cos(rz), 0],
        [0,           0,          1]
    ])
    return Rz @ Ry @ Rx

class TestSVDRegistration(unittest.TestCase):

    def setUp(self):
        # 典型的 4 标记球刚体手术探针模型 (mm)
        self.model_points = np.array([
            [  0.0,   0.0,   0.0],
            [ 45.0,  30.0,   0.0],
            [-45.0,  30.0,   0.0],
            [  0.0,  70.0,  15.0]
        ], dtype=np.float64)
        self.tip_offset = np.array([0.0, 150.0, -10.0], dtype=np.float64)

    def test_identity_transform(self):
        """测试单位变换：测量点与模型点完全重合"""
        R, T, fre = register_point_sets_svd(self.model_points, self.model_points)
        self.assertIsNotNone(R)
        np.testing.assert_allclose(R, np.eye(3), atol=1e-7)
        np.testing.assert_allclose(T, np.zeros(3), atol=1e-7)
        self.assertLess(fre, 1e-7)

    def test_known_rigid_transform(self):
        """测试已知旋转与平移 (毫米级空间导航姿态)"""
        true_R = euler_to_matrix(25.0, -15.0, 40.0)
        true_T = np.array([120.5, -85.3, 650.0]) # 相机前方 650mm 处

        # 模拟相机观测到的标记球点集
        measured_points = np.dot(self.model_points, true_R.T) + true_T
        true_tip = np.dot(true_R, self.tip_offset) + true_T

        # 执行 SVD 刚体解算
        R, T, fre = register_point_sets_svd(self.model_points, measured_points)

        self.assertIsNotNone(R)
        self.assertLess(fre, 1e-6)
        np.testing.assert_allclose(R, true_R, atol=1e-5)
        np.testing.assert_allclose(T, true_T, atol=1e-5)

        # 验证刀尖推算精度
        est_tip = np.dot(R, self.tip_offset) + T
        np.testing.assert_allclose(est_tip, true_tip, atol=1e-5)

    def test_noisy_markers_robustness(self):
        """测试加入传感器噪声 (高斯噪声 sigma = 0.05 mm) 时的鲁棒性"""
        true_R = euler_to_matrix(10.0, -20.0, 30.0)
        true_T = np.array([50.0, 30.0, 500.0])

        measured_clean = np.dot(self.model_points, true_R.T) + true_T
        np.random.seed(42)
        noise = np.random.normal(0, 0.05, measured_clean.shape) # 0.05mm 噪声
        measured_noisy = measured_clean + noise

        R, T, fre = register_point_sets_svd(self.model_points, measured_noisy)
        self.assertIsNotNone(R)
        # FRE 应该在噪声量级左右 (小于 0.15mm)
        self.assertLess(fre, 0.15)

    def test_scrambled_correspondence_matching(self):
        """测试标记球乱序输入时的自动对应关系匹配解算"""
        true_R = euler_to_matrix(15.0, 25.0, -10.0)
        true_T = np.array([0.0, 0.0, 600.0])
        measured_points = np.dot(self.model_points, true_R.T) + true_T

        # 将点集顺序打乱: [3, 0, 2, 1]
        scrambled_indices = [3, 0, 2, 1]
        scrambled_measured = measured_points[scrambled_indices]

        # 运行自动排列匹配
        R, T, fre, perm = match_rigid_body_correspondence(self.model_points, scrambled_measured)

        self.assertIsNotNone(R)
        self.assertLess(fre, 1e-6)
        np.testing.assert_allclose(R, true_R, atol=1e-5)
        np.testing.assert_allclose(T, true_T, atol=1e-5)

if __name__ == '__main__':
    unittest.main()

