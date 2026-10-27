#!/bin/bash
# scout-link.sh - temporarily give the wired interface a 192.168.100.x address
# so a Scout sitting on its fallback 192.168.100.100 becomes reachable.
# macOS and Linux. Windows uses scout-link.ps1.
#
# Usage: bash scout-link.sh status|add|remove
#
# add/remove need admin rights. The script asks through the system's own
# password dialog (macOS: osascript, Linux desktop: pkexec, else sudo), so the
# user only has to approve. The address is an alias that disappears on reboot.
# Never touches DHCP, gateway, DNS or Wi-Fi.

NET=192.168.100
SCOUT=$NET.100
STATE="$HOME/.find-scout-link.state"
ACTION="${1:-status}"
OS=$(uname -s)

wired_up() {
    if [ "$OS" = Darwin ]; then
        # Hardware ports that are not Wi-Fi/Bluetooth/bridges, and are active.
        networksetup -listallhardwareports 2>/dev/null | awk '
            /^Hardware Port:/ { port = substr($0, 16) }
            /^Device:/ { if (port !~ /Wi-Fi|AirPort|Bluetooth|Bridge|iPhone|iPad/) print $2 }' |
        while read -r d; do
            ifconfig "$d" 2>/dev/null | grep -q 'status: active' && echo "$d"
        done
    else
        for p in /sys/class/net/*; do
            d=$(basename "$p")
            case "$d" in en*|eth*) ;; *) continue ;; esac
            [ -d "$p/wireless" ] && continue
            [ "$(cat "$p/carrier" 2>/dev/null)" = 1 ] && echo "$d"
        done
    fi
}

link_ips() {  # $1 = device
    if [ "$OS" = Darwin ]; then
        ifconfig "$1" 2>/dev/null | awk -v n="$NET." '$1 == "inet" && index($2, n) == 1 { print $2 }'
    else
        ip -4 -o addr show dev "$1" 2>/dev/null | awk -v n="$NET." '{ split($4, a, "/"); if (index(a[1], n) == 1) print a[1] }'
    fi
}

as_admin() {  # run one command with the system's own permission prompt
    if [ "$OS" = Darwin ]; then
        osascript -e "do shell script \"$*\" with administrator privileges with prompt \"find-scout wants to add/remove a temporary address on the wired network to reach Scout.\"" >/dev/null 2>&1
    elif [ -n "$DISPLAY$WAYLAND_DISPLAY" ] && command -v pkexec >/dev/null; then
        pkexec "$@"
    else
        sudo "$@"
    fi
}

ping_once() {
    if [ "$OS" = Darwin ]; then ping -c 1 -t 1 "$1" >/dev/null 2>&1
    else ping -c 1 -W 1 "$1" >/dev/null 2>&1; fi
}

UP=$(wired_up)
FIRST=$(echo "$UP" | head -n 1)

case "$ACTION" in
status)
    [ -z "$UP" ] && { echo "RESULT: NO_LINK"; exit 2; }
    for d in $UP; do echo "  $d"; done
    HAVE=$(for d in $UP; do link_ips "$d"; done | tr '\n' ' ')
    if [ -n "${HAVE// /}" ]; then echo "RESULT: HAS_IP $HAVE"; exit 0; fi
    echo "RESULT: NO_IP"; exit 1
    ;;
add)
    [ -z "$UP" ] && { echo "RESULT: NO_LINK"; exit 2; }
    HAVE=$(for d in $UP; do link_ips "$d"; done | tr '\n' ' ')
    if [ -n "${HAVE// /}" ]; then echo "RESULT: ALREADY $HAVE"; exit 0; fi
    IP=
    for i in $(seq 10 30); do
        c=$NET.$i
        [ "$c" = "$SCOUT" ] && continue
        ping_once "$c" || { IP=$c; break; }
    done
    [ -z "$IP" ] && { echo "RESULT: FAILED no free address in $NET.10-30"; exit 1; }
    if [ "$OS" = Darwin ]; then
        as_admin /sbin/ifconfig "$FIRST" alias "$IP" netmask 255.255.255.0
    else
        as_admin ip addr add "$IP/24" dev "$FIRST"
    fi || { echo "RESULT: CANCELLED (the permission prompt was declined or failed)"; exit 3; }
    echo "$FIRST $IP" > "$STATE"
    echo "RESULT: ADDED $IP on $FIRST"
    ;;
remove)
    TARGETS=
    if [ -f "$STATE" ]; then
        TARGETS=$(head -n 1 "$STATE")
    else
        # Fall back to any 192.168.100.x on an active wired interface.
        for d in $UP; do for a in $(link_ips "$d"); do TARGETS="$d $a"; break 2; done; done
    fi
    [ -z "$TARGETS" ] && { echo "RESULT: NOTHING_TO_REMOVE"; rm -f "$STATE"; exit 0; }
    set -- $TARGETS
    if [ "$OS" = Darwin ]; then
        as_admin /sbin/ifconfig "$1" -alias "$2"
    else
        as_admin ip addr del "$2/24" dev "$1"
    fi || { echo "RESULT: CANCELLED (the permission prompt was declined or failed)"; exit 3; }
    rm -f "$STATE"
    echo "RESULT: REMOVED $2 on $1"
    ;;
*)
    echo "Usage: bash scout-link.sh status|add|remove"; exit 64
    ;;
esac
