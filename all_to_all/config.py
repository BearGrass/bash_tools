#!/usr/bin/env python3
"""共享配置"""

DURATION = 120
WAIT_SERVER = 30
LOG_DIR = "/tmp/ib_bw"

HOSTS = [
    "10.107.204.66",
    "10.107.204.67",
    "10.107.204.68",
    "10.107.204.69",
    "10.107.204.70",
    "10.107.204.71",
]

IB_DEVS = ["mlx5_cx6_0", "mlx5_cx6_1", "mlx5_cx6_2", "mlx5_cx6_3"]

def get_port(src_i, dst_i, dev_i):
    """唯一端口: 10000 + dev*100 + src*10 + dst"""
    return 10000 + dev_i * 100 + src_i * 10 + dst_i
