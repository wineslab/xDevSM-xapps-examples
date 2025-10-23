# PRB xApp

Example of a Radio Resource Allocation Control (RC) xApp built using the xDevSM framework.

This xApp sends a Control Request containing a `slice-level PRB quota action`.

### Options
```python
  -p <plmn>, --plmn <plmn>
                        PLMN ID
  -s <sst>, --sst <sst>
                        SST
  -d <sd>, --sd <sd>    SD
  -r <min_prb_policy_ratio>, --min_prb_policy_ratio <min_prb_policy_ratio>
                        Minimum PRB Policy Ratio
  -x <max_prb_policy_ratio>, --max_prb_policy_ratio <max_prb_policy_ratio>
                        Maximum PRB Policy Ratio
  -y <dedicated_prb_policy_ratio>, --dedicated_prb_policy_ratio <dedicated_prb_policy_ratio>
                        Dedicated PRB Policy Ratio
```