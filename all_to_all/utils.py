#!/usr/bin/env python3
"""SSH 工具函数"""

import subprocess
import time
import sys

def ts():
    return time.strftime("%H:%M:%S")

def log(msg):
    print(f"[{ts()}] {msg}", flush=True)

def ssh(host, cmd, capture=False, timeout=30):
    """
    执行远程 SSH 命令
    返回: (returncode, stdout) 
    """
    full_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        host,
        cmd
    ]
    try:
        if capture:
            r = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout.strip()
        else:
            r = subprocess.run(full_cmd, timeout=timeout)
            return r.returncode, ""
    except subprocess.TimeoutExpired:
        log(f"ERROR: SSH timeout -> {host}")
        return -1, ""
    except Exception as e:
        log(f"ERROR: SSH failed -> {host}: {e}")
        return -1, ""

def ssh_batch(host, cmds):
    """批量执行命令（合并为一条）"""
    if not cmds:
        return 0, ""
    combined = " && ".join(cmds)
    return ssh(host, combined, timeout=60)

def cleanup_host(host):
    """清理单台主机"""
    ssh(host, "pkill -9 -f ib_write_bw 2>/dev/null || true")

def cleanup_all(hosts):
    """清理所有主机"""
    log("清理所有主机...")
    for h in hosts:
        cleanup_host(h)
    log("清理完成")
