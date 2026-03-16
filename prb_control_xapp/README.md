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
  -g <gnb_target>, --gnb_target <gnb_target>
                        gNB where to send the control request
  --influx_end_point http://<ip>:port
                        influx db endpoint
  --organization <organization>
                        influx db organization
  --token <token>       influx db token
  --bucket <bucket>     influx db bucket
  --redis_end_point <host:port>
                        Redis endpoint
  --query_range <query_range>
                        Range for InfluxDB queries, e.g., -30d for last 30 days
  -t <time_stamp_file>, --time_stamp <time_stamp_file>
                        Records time stamp of control message sent and control ack received in .txt file
  -m, --mock_du_ue_id   Type of ue id to mock, defaults to get_mock_ue_id if not passed
  -u <ue_id>, --ue_id <ue_id>
                        ue id to use when db not available
```