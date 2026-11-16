#!/bin/bash
# Static-split PRB sweep — single-pod version.
#
# Each iteration calls rc_xapp.py once. rc_xapp.py internally sends TWO
# controls: first sd=1 (S2, decreasing slice) with min=min_S2, then 10 s
# later sd=16777215 (S1, increasing slice) with min=min_S1.
#
# That order keeps sum(min_ratio) <= 100 across every grid transition,
# which is required by ran_func_rc.c:1193 (otherwise gNB asserts).
set -u

GNB="gnb_001_001_00000e01"
MIN_S1_VALUES=(20 30 40 50 60 70 80)
MIN_S2_VALUES=(80 70 60 50 40 30 20)
HOLD=60

ts() { date -u +%FT%T.%3NZ; }

echo "$(ts) [sweep] starting on gnb=${GNB}"
for i in "${!MIN_S1_VALUES[@]}"; do
    m1=${MIN_S1_VALUES[$i]}
    m2=${MIN_S2_VALUES[$i]}
    echo "$(ts) [sweep] grid $((i+1))/7 -> min_S1=${m1} min_S2=${m2}"
    python3 /ws/rc_xapp.py \
        -p 00F110 \
        --min_s1 "${m1}" \
        --min_s2 "${m2}" \
        -x 100 \
        -y 0 \
        -g "${GNB}"
    if [ $((i+1)) -lt ${#MIN_S1_VALUES[@]} ]; then
        sleep ${HOLD}
    fi
done
echo "$(ts) [sweep] done"
