# KPM-PRB xApp

Example of a Radio Resource Allocation Control (RC) and KPM xApp built using the xDevSM framework.

This xApp is designed to dynamically manage Physical Resource Block (PRB) allocation to maintain user throughput within a specified limit.

It works by:

1. **Monitoring**: Continuously collecting user throughput measurements via KPM data.

2. **Control**: When the throughput exceeds a predefined threshold, the xApp issues a slice-level PRB quota control action via RC.

3. **Adaptation**: This action reduces the maximum percentage of PRBs allocated to the affected slice by 5% at each step until the user throughput falls back within the acceptable constraint.

### Options
```python
  -r <route_file>, --route_file <route_file>
                        path of xApp route file
  -c <csv_file>, --csv_file <csv_file>
                        path of csv file
  -e <event_trigger_period>, --event_trigger <event_trigger_period>
                        event trigger period in seconds
  -m <max_down_throughput>, --max_down_throughput <max_down_throughput>
                        Max Downlink Throughput in Mb/s
  -n <max_up_throughput>, --max_up_throughput <max_up_throughput>
                        Max Uplink Throughput in Mb/s
  -s <sst>, --sst <sst>
                        SST
  -d <sd>, --sd <sd>    SD
  -l <log_level>, --log_level <log_level>
                        Log level
  -g <gnb_target>, --gnb_target <gnb_target>
                        gNB to subscribe to
```