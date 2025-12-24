#!/usr/bin/env bash
set -euo pipefail

# -------------------------
# 默认参数
# -------------------------
FORMAT="human"
WRAP=1
FILTER_DRIVER=""
FILTER_IFACE=""
TERM_COLS=$(tput cols 2>/dev/null || echo 140)

# 列宽计算
IFACE_W=16
PCI_W=14
DRIVER_W=12
IP_W=28
MODEL_W=$((TERM_COLS - IFACE_W - PCI_W - DRIVER_W - IP_W - 13))
(( MODEL_W < 40 )) && MODEL_W=40

# -------------------------
# Help
# -------------------------
usage() {
cat <<'EOF'
Usage: net-pci-map [options]

Options:
  --format <human|tsv|json>   Output format (default: human)
  --no-wrap                   Do not wrap NIC Model column
  --driver <name>             Filter by driver
  --iface <name>              Show only specific interface
  -h, --help                  Show this help

Examples:
  net-pci-map
  net-pci-map --driver i40e
  net-pci-map --format json
EOF
exit 0
}

# -------------------------
# Parse args
# -------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --format) FORMAT="$2"; shift 2 ;;
        --no-wrap) WRAP=0; shift ;;
        --driver) FILTER_DRIVER="$2"; shift 2 ;;
        --iface) FILTER_IFACE="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# -------------------------
# IP 获取函数
# -------------------------
get_ips() {
    local iface="$1"
    ip -o addr show "$iface" scope global \
      | awk '{print $4}'
}

# -------------------------
# Collect
# -------------------------
collect() {
    for path in /sys/class/net/*; do
        iface=$(basename "$path")
        [[ "$iface" == "lo" ]] && continue
        [[ -n "$FILTER_IFACE" && "$iface" != "$FILTER_IFACE" ]] && continue
        [[ ! -L "/sys/class/net/$iface/device" ]] && continue

        pci_addr=$(basename "$(readlink /sys/class/net/$iface/device)")
        model=$(lspci -s "${pci_addr#0000:}" | sed 's/^[^ ]* //')
        driver=$(ethtool -i "$iface" 2>/dev/null | awk -F': ' '/driver:/ {print $2}')
        ips=$(get_ips "$iface" | tr '\n' ',' | sed 's/,$//')
        [[ -z "$ips" ]] && ips="-"

        [[ -n "$FILTER_DRIVER" && "$driver" != "$FILTER_DRIVER" ]] && continue

        echo "$iface|$pci_addr|$model|$driver|$ips"
    done
}

# -------------------------
# Output: human
# -------------------------
output_human() {
    printf "%-${IFACE_W}s | %-${PCI_W}s | %-${MODEL_W}s | %-${IP_W}s | %-${DRIVER_W}s\n" \
        "Interface" "PCI-ADDR" "NIC Model" "IP Address" "Driver"

    printf "%-${IFACE_W}s-+-%-${PCI_W}s-+-%-${MODEL_W}s-+-%-${IP_W}s-+-%-${DRIVER_W}s\n" \
        "$(printf '%*s' $IFACE_W | tr ' ' '-')" \
        "$(printf '%*s' $PCI_W | tr ' ' '-')" \
        "$(printf '%*s' $MODEL_W | tr ' ' '-')" \
        "$(printf '%*s' $IP_W | tr ' ' '-')" \
        "$(printf '%*s' $DRIVER_W | tr ' ' '-')"

    collect | while IFS='|' read -r iface pci model driver ips; do
        # IP 拆行
        IFS=',' read -ra ip_arr <<< "$ips"
        (( ${#ip_arr[@]} == 0 )) && ip_arr=("-")

        # Model 拆行
        if (( WRAP )); then
            mapfile -t model_arr < <(echo "$model" | fold -s -w "$MODEL_W")
        else
            model_arr=("$model")
        fi

        max_lines=${#model_arr[@]}
        (( ${#ip_arr[@]} > max_lines )) && max_lines=${#ip_arr[@]}

        for ((i=0; i<max_lines; i++)); do
            printf "%-${IFACE_W}s | %-${PCI_W}s | %-${MODEL_W}s | %-${IP_W}s | %-${DRIVER_W}s\n" \
                "${i==0?iface:""}" \
                "${i==0?pci:""}" \
                "${model_arr[i]:-}" \
                "${ip_arr[i]:-}" \
                "${i==0?driver:""}"
        done
    done
}

# -------------------------
# Output: tsv
# -------------------------
output_tsv() {
    echo -e "Interface\tPCI-ADDR\tNIC-Model\tIP\tDriver"
    collect | awk -F'|' '{print $1 "\t" $2 "\t" $3 "\t" $5 "\t" $4}'
}

# -------------------------
# Output: json
# -------------------------
output_json() {
    echo "["
    first=1
    collect | while IFS='|' read -r iface pci model driver ips; do
        (( first )) || echo ","
        first=0
        cat <<EOF
  {
    "interface": "$iface",
    "pci_addr": "$pci",
    "model": "$model",
    "driver": "$driver",
    "ip": [$(printf '"%s",' ${ips//,/ } | sed 's/,$//')]
  }
EOF
    done
    echo "]"
}

# -------------------------
# Main
# -------------------------
case "$FORMAT" in
    human) output_human ;;
    tsv) output_tsv ;;
    json) output_json ;;
    *) echo "Invalid format: $FORMAT"; exit 1 ;;
esac
