# KPM xApp

Example of kpm xapp built using the xDevSM framework

This xApp can store KPM data in CSV files and InfluxDB. It subscribes to a single E2 node, which can be specified as an input parameter or defaults to the first available node to reply.


### Options
```python
  -s <sst>, --sst <sst>
                        SST
  -d <sd>, --sd <sd>    SD
  -i http://<ip>:port, --influx_end_point http://<ip>:port
                        influx db endpoint
  -o <organization>, --organization <organization>
                        influx db organization
  -t <token>, --token <token>
                        influx db token
  -b <bucket>, --bucket <bucket>
                        influx db bucket
  -r <route_file>, --route_file <route_file>
                        path of xApp route file
  -c <csv_file>, --csv_file <csv_file>
                        path of csv file
  -g <gnb_target>, --gnb_target <gnb_target>
                        gNB to subscribe to
```
