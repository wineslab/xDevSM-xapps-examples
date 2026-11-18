# CCC REPORT xApp

Minimal E2SM-CCC xApp built with the xDevSM framework.

The xApp subscribes one E2 node (the DU) to a cell-level REPORT (REPORT Style 2) on `O-NRCellDU` and logs each indication. It subscribes to the node given with `-g`, or to the first connected E2 node. If the gNB has a CU/DU split, use `-g` to select the DU. The RAN function ID comes from the CCC OID that the node announces.

The DU reports the selected attributes of every cell. The default period is 1000 ms, and the default attributes are `arfcnDL`, `bSChannelBwDL` and `bWPList`.

### Options
```
  -p <ms>, --period-ms <ms>
                        report period, at least 10 ms
  -a <attr1,attr2,...>, --attributes <attr1,attr2,...>
                        comma-separated O-NRCellDU attributes to report (default: arfcnDL,bSChannelBwDL,bWPList)
  -r <route_file>, --route_file <route_file>
                        path of xApp route file
  -g <gnb_target>, --gnb_target <gnb_target>
                        gNB to subscribe to
```
