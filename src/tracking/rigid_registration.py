import itertools
from typing import Tuple, Optional
import numpy as np

def register_point_sets_svd(
    model_points: np.ndarray,
    measured_points: np.ndarray
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], float]:
    """
    Kabsch / Arun's SVD 刚体配准算法 (对应 SciKit-Surgery / NDI Polaris 核心算法)
    
    已知两个对应点集 (顺序已对齐):
        model_points: 刚体本地 CAD 模型坐标 (N x 3)
        measured_points: 视觉测量到的 3D 坐标 (N x 3)
        
    返回:
        R: 3x3 旋转矩阵 (从 model 到 measured)
        T: 3x1 平移向量 (从 model 到 measured, 单位与输入一致，通常为 mm)
        fre: 标记点配准均方根误差 (Fiducial Registration Error, mm)
    """
    if len(model_points) < 3 or len(measured_points) < 3:
        return None, None, float("inf")

    n = min(len(model_points), len(measured_points))
    M = np.asarray(model_points[:n], dtype=np.float64)
    P = np.asarray(measured_points[:n], dtype=np.float64)

    # 1. 计算点集质心
    centroid_M = np.mean(M, axis=0)
    centroid_P = np.mean(P, axis=0)

    # 2. 去质心化中心对齐
    M_centered = M - centroid_M
    P_centered = P - centroid_P

    # 3. 构造 3x3 协方差矩阵 H
    H = np.dot(M_centered.T, P_centered)

    # 4. SVD 奇异值分解
    U, S, Vt = np.linalg.svd(H)
    V = Vt.T
    
    # 5. 旋转矩阵解算 (并解决可能的镜像/反射二义性 det(R) == -1)
    d = np.linalg.det(np.dot(V, U.T))
    diag = np.diag([1.0, 1.0, 1.0 if d >= 0 else -1.0])
    R = np.dot(np.dot(V, diag), U.T)

    # 6. 平移向量解算
    T = centroid_P - np.dot(R, centroid_M)

    # 7. 计算 FRE (Fiducial Registration Error)
    M_transformed = np.dot(M, R.T) + T
    residuals = P - M_transformed
    fre = float(np.sqrt(np.mean(np.sum(residuals ** 2, axis=1))))

    return R, T, fre

def match_rigid_body_correspondence(
    model_points: np.ndarray,
    measured_points: np.ndarray,
    max_fre_threshold: float = 3.0
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], float, Optional[list]]:
    """
    无序标记点全排列对应关系解算器 (Marker Correspondence Matching)
    
    当相机检测到的 N 个反光球空间坐标顺序未知时，在所有排列组合中寻找 FRE 最小且低于阈值的最优配对。
    
    返回:
        (best_R, best_T, best_fre, best_perm)
    """
    m_len = len(model_points)
    p_len = len(measured_points)

    if p_len < m_len or m_len < 3:
        return None, None, float("inf"), None

    best_fre = float("inf")
    best_R = None
    best_T = None
    best_perm = None

    # 对视觉检测到的点取 m_len 个的所有排列 (一般探针有 4 个球，排列数极少，单帧耗时 < 0.1ms)
    indices = list(range(p_len))
    for perm in itertools.permutations(indices, m_len):
        perm_measured = measured_points[list(perm)]
        R, T, fre = register_point_sets_svd(model_points, perm_measured)
        if R is not None and fre < best_fre:
            best_fre = fre
            best_R = R
            best_T = T
            best_perm = list(perm)

            if best_fre < 0.2: # 已达到极佳匹配，提前剪枝
                break

    if best_fre <= max_fre_threshold:
        return best_R, best_T, best_fre, best_perm
    else:
        return None, None, best_fre, None

