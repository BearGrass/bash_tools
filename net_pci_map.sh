#!/usr/bin/env bash

printf "%-12s %-14s %-55s %-20s\n" "Interface" "PCI-ADDR" "NIC Model" "Driver"
printf "%-12s %-14s %-55s %-20s\n" "---------" "--------" "---------" "------"

for iface in $(ls /sys/class/net); do
    [[ "$iface" == "lo" ]] && continue

    if [[ -L "/sys/class/net/$iface/device" ]]; then
        pci_addr=$(basename "$(readlink /sys/class/net/$iface/device)")

        nic_model=$(lspci -s "${pci_addr#0000:}" | sed 's/^[^ ]* //')

        driver=$(ethtool -i "$iface" 2>/dev/null | awk -F': ' '/driver:/ {print $2}')

        printf "%-12s %-14s %-55s %-20s\n" \
            "$iface" "$pci_addr" "${nic_model:-N/A}" "${driver:-N/A}"
    fi
done
