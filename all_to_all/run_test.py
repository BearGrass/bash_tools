#!/usr/bin/env python3
"""All-to-All IB 带宽压测"""

import sys
import time
import signal
from config import HOSTS, IB_DEVS, DURATION, WAIT_SERVER, LOG_DIR, get_port
from utils import log, ssh, ssh_batch, cleanup_all

# Ctrl+C 处理
def signal_handler(sig, frame):
    log("收到中断信号，清理中...")
    cleanup_all(HOSTS)
    sys.exit(1)

signal.signal(signal.SIGINT, signal_handler)

def prepare():
    """准备所有主机"""
    log("=== 阶段1: 准备主机 ===")
    for h in HOSTS:
        cmd = f"pkill -9 -f ib_write_bw; sleep 1; mkdir -p {LOG_DIR}; rm -f {LOG_DIR}/*.log"
        rc, _ = ssh(h, cmd)
        status = "OK" if rc == 0 else "FAIL"
        log(f"  {h}: {status}")
    log("准备完成\n")

def start_servers():
    """启动所有 server"""
    log("=== 阶段2: 启动 Server ===")
    
    for dst_i, dst in enumerate(HOSTS):
        cmds = []
        for src_i, src in enumerate(HOSTS):
            if src == dst:
                continue
            for dev_i, dev in enumerate(IB_DEVS):
                port = get_port(src_i, dst_i, dev_i)
                cmd = (
                    f"nohup timeout {DURATION + 60}s "
                    f"ib_write_bw -F --report_gbits --ib-dev={dev} "
                    f"--run_infinitely -D1 -p {port} -q 8 "
                    f"> {LOG_DIR}/srv_{port}.log 2>&1 &"
                )
                cmds.append(cmd)
        
        rc, _ = ssh_batch(dst, cmds)
        status = "OK" if rc == 0 else "FAIL"
        log(f"  {dst}: {len(cmds)} servers - {status}")
    
    log(f"等待 server 就绪 ({WAIT_SERVER}s)...\n")
    time.sleep(WAIT_SERVER)

def start_clients():
    """启动所有 client"""
    log("=== 阶段3: 启动 Client ===")
    
    for src_i, src in enumerate(HOSTS):
        cmds = []
        for dst_i, dst in enumerate(HOSTS):
            if src == dst:
                continue
            for dev_i, dev in enumerate(IB_DEVS):
                port = get_port(src_i, dst_i, dev_i)
                cmd = (
                    f"nohup timeout {DURATION}s "
                    f"ib_write_bw -F --report_gbits --ib-dev={dev} "
                    f"--run_infinitely -D1 -p {port} -q 8 {dst} "
                    f"> {LOG_DIR}/cli_{dev}_{port}.log 2>&1 &"
                )
                cmds.append(cmd)
        
        rc, _ = ssh_batch(src, cmds)
        status = "OK" if rc == 0 else "FAIL"
        log(f"  {src}: {len(cmds)} clients - {status}")
    
    log("")

def wait_test():
    """等待测试完成"""
    log(f"=== 阶段4: 压测进行中 ({DURATION}s) ===")
    
    interval = 10
    for i in range(DURATION // interval):
        elapsed = (i + 1) * interval
        print(f"\r  {elapsed}s / {DURATION}s", end="", flush=True)
        time.sleep(interval)
    
    print(f"\r  {DURATION}s / {DURATION}s - 完成")
    log("等待进程退出...\n")
    time.sleep(15)

def collect_results():
    """收集并汇总结果"""
    log("=== 阶段5: 收集结果 ===")
    
    results = []
    for src_i, src in enumerate(HOSTS):
        for dst_i, dst in enumerate(HOSTS):
            if src == dst:
                continue
            for dev_i, dev in enumerate(IB_DEVS):
                port = get_port(src_i, dst_i, dev_i)
                logf = f"{LOG_DIR}/cli_{dev}_{port}.log"
                
                # 提取最后一行有效数据
                cmd = f"tail -5 {logf} 2>/dev/null | grep -E '^\\s*[0-9]' | tail -1"
                rc, out = ssh(src, cmd, capture=True)
                
                gbps = None
                if out:
                    parts = out.split()
                    if len(parts) >= 4:
                        try:
                            gbps = float(parts[-1])
                        except ValueError:
                            pass
                
                results.append({
                    "src": src, "dst": dst, "dev": dev,
                    "port": port, "gbps": gbps
                })
    
    return results

def print_summary(results):
    """打印结果汇总"""
    print("\n" + "=" * 75)
    print("结果汇总")
    print("=" * 75)
    print(f"{'源主机':<17} {'设备':<13} {'目标主机':<17} {'带宽(Gbps)':<10}")
    print("-" * 75)
    
    total, success, failed = 0.0, 0, 0
    failed_list = []
    
    for r in sorted(results, key=lambda x: (x["src"], x["dst"], x["dev"])):
        src, dst, dev, gbps = r["src"], r["dst"], r["dev"], r["gbps"]
        
        if gbps is not None:
            print(f"{src:<17} {dev:<13} {dst:<17} {gbps:.2f}")
            total += gbps
            success += 1
        else:
            print(f"{src:<17} {dev:<13} {dst:<17} {'N/A'}")
            failed += 1
            failed_list.append(f"{src}[{dev}]->{dst}")
    
    print("-" * 75)
    print(f"成功: {success}, 失败: {failed}, 总带宽: {total:.2f} Gbps", end="")
    if success > 0:
        print(f", 平均: {total/success:.2f} Gbps")
    else:
        print()
    
    # 按主机汇总
    print("\n按主机出站带宽:")
    host_bw = {}
    for r in results:
        src = r["src"]
        if src not in host_bw:
            host_bw[src] = 0.0
        if r["gbps"]:
            host_bw[src] += r["gbps"]
    
    for h in sorted(host_bw.keys()):
        print(f"  {h}: {host_bw[h]:.2f} Gbps")
    
    if failed_list:
        print(f"\n失败列表 (前10个):")
        for f in failed_list[:10]:
            print(f"  - {f}")
    
    print("=" * 75)

def main():
    n_conn = len(HOSTS) * (len(HOSTS) - 1) * len(IB_DEVS)
    log(f"All-to-All 压测: {len(HOSTS)} 主机, {len(IB_DEVS)} 设备, {n_conn} 连接\n")
    
    prepare()
    start_servers()
    start_clients()
    wait_test()
    
    results = collect_results()
    print_summary(results)
    
    cleanup_all(HOSTS)
    log("测试完成")

if __name__ == "__main__":
    main()
