```python
from utils import (
    _to_dict,
    _donut,
    _pie,
    _line_graph,
    _other_fields,
    _exitcode_info
)
from datetime import datetime, date, timedelta
from pyspark.sql.functions import (
    col,
    lit,
    when,
    sum as _sum,
    count as _count,
    first,
    date_format,
    from_unixtime,
    to_date
)
import numpy as np
import pandas as pd
from pyspark.sql.types import (
    StructType,
    LongType,
    StringType,
    StructField,
    DoubleType,
    IntegerType,
)
```

Which are the 5 (10) most used datasets[DESIRED_CMSDataset] in the last week/month[RecordTime]... etc. ? How much CPU time[CpuTimeHr]*[RequestCpus]=[CoreHr],[WallClockHr] was spent on those ? Which fraction of the total ? How big are those ?[Size] How many users/tasks hit each dataset ?[User][CRAB_LumiMask]


```python
def _get_schema():
    return StructType(
        [
            StructField(
                "data",
                StructType(
                    [
                        StructField("RecordTime", LongType(), nullable=False),
                        StructField("InputData", StringType(), nullable=True),
                        StructField("Status", StringType(), nullable=True),
                        StructField("DESIRED_CMSDataset", StringType(), nullable=True),
                        StructField("CpuTimeHr", DoubleType(), nullable=True),
                        StructField("RequestCpus", LongType(), nullable=True),
                        StructField("GlobalJobId", StringType(), nullable=False),
                        StructField("CMS_SubmissionTool", StringType(), nullable=True)
                    ]
                ),
            ),
        ]
    )
```


```python
_DEFAULT_HDFS_FOLDER = "/project/monitoring/archive/condor/raw/metric"
```


```python
def get_candidate_files(start_date, end_date, spark, base=_DEFAULT_HDFS_FOLDER):
    st_date = start_date - timedelta(days=3)
    ed_date = end_date + timedelta(days=3)
    days = (ed_date - st_date).days
    pre_candidate_files = [
        "{base}/{day}{{,.tmp}}".format(
            base=base, day=(st_date + timedelta(days=i)).strftime("%Y/%m/%d")
        )
        for i in range(0, days)
    ]
    sc = spark.sparkContext
    candidate_files = [
        f"{base}/{(st_date + timedelta(days=i)).strftime('%Y/%m/%d')}"
        for i in range(0, days)
    ]
    FileSystem = sc._gateway.jvm.org.apache.hadoop.fs.FileSystem
    URI = sc._gateway.jvm.java.net.URI
    Path = sc._gateway.jvm.org.apache.hadoop.fs.Path
    fs = FileSystem.get(URI("hdfs:///"), sc._jsc.hadoopConfiguration())
    candidate_files = [url for url in candidate_files if fs.globStatus(Path(url))]
    return candidate_files

```


```python
schema = _get_schema()
start_date = datetime(2022, 5, 1)
end_date = datetime(2022, 5, 8)
```


```python
get_candidate_files(start_date, end_date, spark, base=_DEFAULT_HDFS_FOLDER)
```




    ['/project/monitoring/archive/condor/raw/metric/2022/04/28',
     '/project/monitoring/archive/condor/raw/metric/2022/04/29',
     '/project/monitoring/archive/condor/raw/metric/2022/04/30',
     '/project/monitoring/archive/condor/raw/metric/2022/05/01',
     '/project/monitoring/archive/condor/raw/metric/2022/05/02',
     '/project/monitoring/archive/condor/raw/metric/2022/05/03',
     '/project/monitoring/archive/condor/raw/metric/2022/05/04',
     '/project/monitoring/archive/condor/raw/metric/2022/05/05',
     '/project/monitoring/archive/condor/raw/metric/2022/05/06',
     '/project/monitoring/archive/condor/raw/metric/2022/05/07',
     '/project/monitoring/archive/condor/raw/metric/2022/05/08',
     '/project/monitoring/archive/condor/raw/metric/2022/05/09',
     '/project/monitoring/archive/condor/raw/metric/2022/05/10']




```python
raw_df = (
        spark.read.option("basePath", _DEFAULT_HDFS_FOLDER)
        .json(
            get_candidate_files(start_date, end_date, spark, base=_DEFAULT_HDFS_FOLDER),
            schema=schema,
        ).select("data.*")
        .filter(
            f"""RecordTime >= {start_date.timestamp() * 1000}
          AND RecordTime < {end_date.timestamp() * 1000}
          """
        )
        .drop_duplicates(["GlobalJobId"])
    )

spark.conf.set("spark.sql.session.timeZone", "UTC")
```


```python
raw_df.printSchema()
```

    root
     |-- RecordTime: long (nullable = true)
     |-- InputData: string (nullable = true)
     |-- Status: string (nullable = true)
     |-- DESIRED_CMSDataset: string (nullable = true)
     |-- CpuTimeHr: double (nullable = true)
     |-- RequestCpus: long (nullable = true)
     |-- GlobalJobId: string (nullable = true)
     |-- CMS_SubmissionTool: string (nullable = true)
    



```python
x = raw_df.select(col('CMS_SubmissionTool')).distinct().show()
```

    +-------------------+
    | CMS_SubmissionTool|
    +-------------------+
    |               CRAB|
    |InstitutionalSchedd|
    |         CMSConnect|
    |            WMAgent|
    |          Condor_SI|
    +-------------------+
    


### df1 - time range 05/01 - 05/08 (7days)


```python
df1 = raw_df.withColumn("timestamp", date_format(from_unixtime(col('RecordTime')/1000), "dd"))\
            .select(col('timestamp'),\
                    col('DESIRED_CMSDataset'),\
                    col('CpuTimeHr'))\
            .groupby(col('timestamp'), col('DESIRED_CMSDataset'))\
            .agg(_sum("CpuTimeHr").alias("Sum_CpuTimeHr"))\

```


```python
df1.printSchema()
```

    root
     |-- timestamp: string (nullable = true)
     |-- DESIRED_CMSDataset: string (nullable = true)
     |-- Sum_CpuTimeHr: double (nullable = true)
    



```python
df1.select(col('timestamp')).distinct().show()
```

    +---------+
    |timestamp|
    +---------+
    |       07|
    |       30|
    |       01|
    |       05|
    |       03|
    |       02|
    |       06|
    |       04|
    +---------+
    



```python
import pyspark.sql.functions as F     
week_Sum = df1.agg(F.sum("Sum_CpuTimeHr")).collect()[0][0]
```


```python
daily_Sum_CpuTimeHr = df1.groupby(col('timestamp')).agg(F.sum("Sum_CpuTimeHr")).orderBy(col('timestamp')).collect()
```


```python
daily_Sum_CpuTimeHr
```




    [Row(timestamp='01', sum(Sum_CpuTimeHr)=3237665.5605555526),
     Row(timestamp='02', sum(Sum_CpuTimeHr)=2405833.891111112),
     Row(timestamp='03', sum(Sum_CpuTimeHr)=2780124.6286111106),
     Row(timestamp='04', sum(Sum_CpuTimeHr)=1640770.8308333335),
     Row(timestamp='05', sum(Sum_CpuTimeHr)=1856863.838611111),
     Row(timestamp='06', sum(Sum_CpuTimeHr)=2425978.531666666),
     Row(timestamp='07', sum(Sum_CpuTimeHr)=2002801.1166666658),
     Row(timestamp='30', sum(Sum_CpuTimeHr)=570767.4969444439)]




```python
df1.createOrReplaceTempView("df1")
```


```python
daily_Top5_CpuTimeHr = spark.sql("(SELECT * FROM df1 WHERE df1.timestamp=='30' ORDER BY df1.Sum_CpuTimeHr DESC LIMIT 5)\
                        UNION ALL (SELECT * FROM df1 WHERE df1.timestamp=='01' ORDER BY df1.Sum_CpuTimeHr DESC LIMIT 5)\
                        UNION ALL (SELECT * FROM df1 WHERE df1.timestamp=='02' ORDER BY df1.Sum_CpuTimeHr DESC LIMIT 5)\
                        UNION ALL (SELECT * FROM df1 WHERE df1.timestamp=='03' ORDER BY df1.Sum_CpuTimeHr DESC LIMIT 5)\
                        UNION ALL (SELECT * FROM df1 WHERE df1.timestamp=='04' ORDER BY df1.Sum_CpuTimeHr DESC LIMIT 5)\
                        UNION ALL (SELECT * FROM df1 WHERE df1.timestamp=='05' ORDER BY df1.Sum_CpuTimeHr DESC LIMIT 5)\
                        UNION ALL (SELECT * FROM df1 WHERE df1.timestamp=='06' ORDER BY df1.Sum_CpuTimeHr DESC LIMIT 5)\
                        UNION ALL (SELECT * FROM df1 WHERE df1.timestamp=='07' ORDER BY df1.Sum_CpuTimeHr DESC LIMIT 5)")
```


```python
Labels = ['May 1st Week', '30/04', '01/05','02/05', '03/05', '04/05', '05/05', '06/05', '07/05']
for i in ['30', '01', '02', '03', '04', '05', '06', '07']:
    for j in range(1, 6):
        Labels.append('%s - Top%d' % (i, j))
```


```python
Values = [week_Sum]
Values.append(daily_Sum_CpuTimeHr[7]['sum(Sum_CpuTimeHr)'])
for i in daily_Sum_CpuTimeHr:
    if(i['timestamp']=='30'):
        break
    else:
        Values.append(i['sum(Sum_CpuTimeHr)'])
Values.extend(daily_Top5_CpuTimeHr_list)
```


```python
Parents = [""]
for i in range(8):
    Parents.append("May 1st Week")
for k in ['30/04', '01/05','02/05', '03/05', '04/05', '05/05', '06/05', '07/05']:
    for j in range(5):
        Parents.append(k)
```


```python
Hover = ['May 1st Week', '30/04', '01/05','02/05', '03/05', '04/05', '05/05', '06/05', '07/05']
Hover.extend(daily_Top5_Dataset_list)
for i in range(49):
    x = " - CPU Time: %.3f"%(Values[i])
    Hover[i] = f'{Hover[i]}{x}'
```


```python
x = sum(Values)-Values[0]
```


```python
x - Values[0]
```




    -97856.37749999762




```python
daily_Top5_CpuTimeHr_list = daily_Top5_CpuTimeHr.select('Sum_CpuTimeHr').rdd.flatMap(lambda x: x).collect()
```




```python
daily_Top5_Dataset_list = daily_Top5_CpuTimeHr.select('DESIRED_CMSDataset').rdd.flatMap(lambda x: x).collect()
```




```python
for i in range(len(daily_Top5_Dataset_list)):
    if (daily_Top5_Dataset_list[i] is None):
        daily_Top5_Dataset_list[i] = "Null"
        
```


```python
import plotly.graph_objects as go

fig =go.Figure(go.Sunburst(
    labels=Labels,
    parents=Parents,
    values=Values,
    hovertemplate=Hover,
    name=""
))
fig.update_layout(margin = dict(t=0, l=0, r=0, b=0))

fig.show()
```


<div>


            <div id="3a6b3126-7240-481c-86ac-38a8ae6ddcdf" class="plotly-graph-div" style="height:525px; width:100%;"></div>
            <script type="text/javascript">
                require(["plotly"], function(Plotly) {
                    window.PLOTLYENV=window.PLOTLYENV || {};

                if (document.getElementById("3a6b3126-7240-481c-86ac-38a8ae6ddcdf")) {
                    Plotly.newPlot(
                        '3a6b3126-7240-481c-86ac-38a8ae6ddcdf',
                        [{"hovertemplate": ["May 1st Week - CPU Time: 17230754.609", "30/04 - CPU Time: 570767.497", "01/05 - CPU Time: 3237665.561", "02/05 - CPU Time: 2405833.891", "03/05 - CPU Time: 2780124.629", "04/05 - CPU Time: 1640770.831", "05/05 - CPU Time: 1856863.839", "06/05 - CPU Time: 2425978.532", "07/05 - CPU Time: 2002801.117", "Null - CPU Time: 525436.415", "/TTJets_TuneCP5_13TeV-amcatnloFXFX-pythia8/RunIISummer20UL17MiniAOD-106X_mc2017_realistic_v6-v2/MINIAODSIM - CPU Time: 8444.535", "/MuOnia/Run2018A-v1/RAW - CPU Time: 7913.050", "/Charmonium/Run2018A-v1/RAW - CPU Time: 5497.065", "/TTToSemiLeptonic_TuneCP5_13TeV-powheg-pythia8/RunIISummer20UL17MiniAOD-106X_mc2017_realistic_v6-v2/MINIAODSIM - CPU Time: 4336.978", "Null - CPU Time: 2391008.125", "/MuOnia/Run2018A-v1/RAW - CPU Time: 35902.691", "/Tau/Run2018A-v1/RAW - CPU Time: 33715.245", "/Tau/Run2018B-v1/RAW - CPU Time: 28417.584", "/Tau/Run2018C-v1/RAW - CPU Time: 22874.277", "Null - CPU Time: 1914446.371", "/EGamma/Run2018C-v1/RAW - CPU Time: 30692.127", "/Tau/Run2018A-v1/RAW - CPU Time: 27810.123", "/Charmonium/Run2018D-v1/RAW - CPU Time: 22828.950", "/SingleMuon/Run2018A-UL2018_MiniAODv2-v3/MINIAOD - CPU Time: 22618.157", "Null - CPU Time: 2324922.709", "/EGamma/Run2018C-v1/RAW - CPU Time: 61326.856", "/EGamma/Run2018D-12Nov2019_UL2018-v4/MINIAOD - CPU Time: 32056.297", "/Tau/Run2018A-v1/RAW - CPU Time: 24778.929", "/TTToSemiLeptonic_TuneCP5_13TeV-powheg-pythia8/RunIISummer20UL18MiniAODv2-106X_upgrade2018_realistic_v16_L1v1-v2/MINIAODSIM - CPU Time: 23074.572", "Null - CPU Time: 1220947.469", "/PMSSM_set_2_LL_2_TuneCP2_13TeV-pythia8/RunIIFall17MiniAODv2-PUFall17Fast_GridpackScan_94X_mc2017_realistic_v15-v2/MINIAODSIM - CPU Time: 22284.813", "/EGamma/Run2018D-12Nov2019_UL2018-v4/MINIAOD - CPU Time: 18760.714", "/EGamma/Run2018C-v1/RAW - CPU Time: 16905.317", "/Tau/Run2018A-v1/RAW - CPU Time: 11880.745", "Null - CPU Time: 1361493.080", "/EGamma/Run2018D-v1/RAW - CPU Time: 69892.197", "/PMSSM_set_2_LL_2_TuneCP2_13TeV-pythia8/RunIIFall17MiniAODv2-PUFall17Fast_GridpackScan_94X_mc2017_realistic_v15-v2/MINIAODSIM - CPU Time: 17037.596", "/PMSSM_set_2_prompt_1_TuneCP2_13TeV-pythia8/RunIIAutumn18MiniAOD-PUFall18Fast_GridpackScan_102X_upgrade2018_realistic_v15-v4/MINIAODSIM - CPU Time: 15396.829", "/EGamma/Run2018D-12Nov2019_UL2018-v4/MINIAOD - CPU Time: 9300.392", "Null - CPU Time: 1940074.206", "/EGamma/Run2018D-v1/RAW - CPU Time: 262771.892", "/SingleMuon/Run2018D-15Feb2022_UL2018-v1/AOD - CPU Time: 18780.260", "/ExpressCosmics/Commissioning2022-Express-v1/FEVT - CPU Time: 18372.974", "/EGamma/Run2018D-12Nov2019_UL2018-v4/MINIAOD - CPU Time: 13712.946", "Null - CPU Time: 1640172.343", "/EGamma/Run2018D-v1/RAW - CPU Time: 20160.249", "/PMSSM_set_2_prompt_1_TuneCP2_13TeV-pythia8/RunIIFall17MiniAODv2-PUFall17Fast_GridpackScan_94X_mc2017_realistic_v15-v2/MINIAODSIM - CPU Time: 13416.153", "/EGamma/Run2018D-12Nov2019_UL2018-v4/MINIAOD - CPU Time: 11940.400", "/SingleMuon/Run2018D-15Feb2022_UL2018-v1/AOD - CPU Time: 7905.396"], "labels": ["May 1st Week", "30/04", "01/05", "02/05", "03/05", "04/05", "05/05", "06/05", "07/05", "30 - Top1", "30 - Top2", "30 - Top3", "30 - Top4", "30 - Top5", "01 - Top1", "01 - Top2", "01 - Top3", "01 - Top4", "01 - Top5", "02 - Top1", "02 - Top2", "02 - Top3", "02 - Top4", "02 - Top5", "03 - Top1", "03 - Top2", "03 - Top3", "03 - Top4", "03 - Top5", "04 - Top1", "04 - Top2", "04 - Top3", "04 - Top4", "04 - Top5", "05 - Top1", "05 - Top2", "05 - Top3", "05 - Top4", "05 - Top5", "06 - Top1", "06 - Top2", "06 - Top3", "06 - Top4", "06 - Top5", "07 - Top1", "07 - Top2", "07 - Top3", "07 - Top4", "07 - Top5"], "name": "", "parents": ["", "May 1st Week", "May 1st Week", "May 1st Week", "May 1st Week", "May 1st Week", "May 1st Week", "May 1st Week", "May 1st Week", "30/04", "30/04", "30/04", "30/04", "30/04", "01/05", "01/05", "01/05", "01/05", "01/05", "02/05", "02/05", "02/05", "02/05", "02/05", "03/05", "03/05", "03/05", "03/05", "03/05", "04/05", "04/05", "04/05", "04/05", "04/05", "05/05", "05/05", "05/05", "05/05", "05/05", "06/05", "06/05", "06/05", "06/05", "06/05", "07/05", "07/05", "07/05", "07/05", "07/05"], "type": "sunburst", "values": [17230754.609444443, 570767.4969444439, 3237665.5605555526, 2405833.891111112, 2780124.6286111106, 1640770.8308333335, 1856863.838611111, 2425978.531666666, 2002801.1166666658, 525436.4152777776, 8444.535, 7913.049722222222, 5497.0647222222215, 4336.977777777776, 2391008.1249999995, 35902.691388888896, 33715.24527777778, 28417.583888888887, 22874.27722222223, 1914446.3705555557, 30692.126944444448, 27810.1225, 22828.949722222223, 22618.157222222228, 2324922.7091666684, 61326.85555555555, 32056.296666666654, 24778.9288888889, 23074.572222222214, 1220947.469444445, 22284.81305555556, 18760.713888888895, 16905.316944444443, 11880.74472222222, 1361493.0799999994, 69892.19666666664, 17037.59638888889, 15396.828611111123, 9300.392222222219, 1940074.2055555556, 262771.8916666667, 18780.260277777776, 18372.974444444437, 13712.94555555555, 1640172.3425, 20160.249444444456, 13416.15277777778, 11940.400277777779, 7905.396388888889]}],
                        {"margin": {"b": 0, "l": 0, "r": 0, "t": 0}, "template": {"data": {"bar": [{"error_x": {"color": "#2a3f5f"}, "error_y": {"color": "#2a3f5f"}, "marker": {"line": {"color": "#E5ECF6", "width": 0.5}}, "type": "bar"}], "barpolar": [{"marker": {"line": {"color": "#E5ECF6", "width": 0.5}}, "type": "barpolar"}], "carpet": [{"aaxis": {"endlinecolor": "#2a3f5f", "gridcolor": "white", "linecolor": "white", "minorgridcolor": "white", "startlinecolor": "#2a3f5f"}, "baxis": {"endlinecolor": "#2a3f5f", "gridcolor": "white", "linecolor": "white", "minorgridcolor": "white", "startlinecolor": "#2a3f5f"}, "type": "carpet"}], "choropleth": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "choropleth"}], "contour": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "colorscale": [[0.0, "#0d0887"], [0.1111111111111111, "#46039f"], [0.2222222222222222, "#7201a8"], [0.3333333333333333, "#9c179e"], [0.4444444444444444, "#bd3786"], [0.5555555555555556, "#d8576b"], [0.6666666666666666, "#ed7953"], [0.7777777777777778, "#fb9f3a"], [0.8888888888888888, "#fdca26"], [1.0, "#f0f921"]], "type": "contour"}], "contourcarpet": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "contourcarpet"}], "heatmap": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "colorscale": [[0.0, "#0d0887"], [0.1111111111111111, "#46039f"], [0.2222222222222222, "#7201a8"], [0.3333333333333333, "#9c179e"], [0.4444444444444444, "#bd3786"], [0.5555555555555556, "#d8576b"], [0.6666666666666666, "#ed7953"], [0.7777777777777778, "#fb9f3a"], [0.8888888888888888, "#fdca26"], [1.0, "#f0f921"]], "type": "heatmap"}], "heatmapgl": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "colorscale": [[0.0, "#0d0887"], [0.1111111111111111, "#46039f"], [0.2222222222222222, "#7201a8"], [0.3333333333333333, "#9c179e"], [0.4444444444444444, "#bd3786"], [0.5555555555555556, "#d8576b"], [0.6666666666666666, "#ed7953"], [0.7777777777777778, "#fb9f3a"], [0.8888888888888888, "#fdca26"], [1.0, "#f0f921"]], "type": "heatmapgl"}], "histogram": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "histogram"}], "histogram2d": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "colorscale": [[0.0, "#0d0887"], [0.1111111111111111, "#46039f"], [0.2222222222222222, "#7201a8"], [0.3333333333333333, "#9c179e"], [0.4444444444444444, "#bd3786"], [0.5555555555555556, "#d8576b"], [0.6666666666666666, "#ed7953"], [0.7777777777777778, "#fb9f3a"], [0.8888888888888888, "#fdca26"], [1.0, "#f0f921"]], "type": "histogram2d"}], "histogram2dcontour": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "colorscale": [[0.0, "#0d0887"], [0.1111111111111111, "#46039f"], [0.2222222222222222, "#7201a8"], [0.3333333333333333, "#9c179e"], [0.4444444444444444, "#bd3786"], [0.5555555555555556, "#d8576b"], [0.6666666666666666, "#ed7953"], [0.7777777777777778, "#fb9f3a"], [0.8888888888888888, "#fdca26"], [1.0, "#f0f921"]], "type": "histogram2dcontour"}], "mesh3d": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "mesh3d"}], "parcoords": [{"line": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "parcoords"}], "pie": [{"automargin": true, "type": "pie"}], "scatter": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scatter"}], "scatter3d": [{"line": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scatter3d"}], "scattercarpet": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scattercarpet"}], "scattergeo": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scattergeo"}], "scattergl": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scattergl"}], "scattermapbox": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scattermapbox"}], "scatterpolar": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scatterpolar"}], "scatterpolargl": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scatterpolargl"}], "scatterternary": [{"marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "type": "scatterternary"}], "surface": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "colorscale": [[0.0, "#0d0887"], [0.1111111111111111, "#46039f"], [0.2222222222222222, "#7201a8"], [0.3333333333333333, "#9c179e"], [0.4444444444444444, "#bd3786"], [0.5555555555555556, "#d8576b"], [0.6666666666666666, "#ed7953"], [0.7777777777777778, "#fb9f3a"], [0.8888888888888888, "#fdca26"], [1.0, "#f0f921"]], "type": "surface"}], "table": [{"cells": {"fill": {"color": "#EBF0F8"}, "line": {"color": "white"}}, "header": {"fill": {"color": "#C8D4E3"}, "line": {"color": "white"}}, "type": "table"}]}, "layout": {"annotationdefaults": {"arrowcolor": "#2a3f5f", "arrowhead": 0, "arrowwidth": 1}, "coloraxis": {"colorbar": {"outlinewidth": 0, "ticks": ""}}, "colorscale": {"diverging": [[0, "#8e0152"], [0.1, "#c51b7d"], [0.2, "#de77ae"], [0.3, "#f1b6da"], [0.4, "#fde0ef"], [0.5, "#f7f7f7"], [0.6, "#e6f5d0"], [0.7, "#b8e186"], [0.8, "#7fbc41"], [0.9, "#4d9221"], [1, "#276419"]], "sequential": [[0.0, "#0d0887"], [0.1111111111111111, "#46039f"], [0.2222222222222222, "#7201a8"], [0.3333333333333333, "#9c179e"], [0.4444444444444444, "#bd3786"], [0.5555555555555556, "#d8576b"], [0.6666666666666666, "#ed7953"], [0.7777777777777778, "#fb9f3a"], [0.8888888888888888, "#fdca26"], [1.0, "#f0f921"]], "sequentialminus": [[0.0, "#0d0887"], [0.1111111111111111, "#46039f"], [0.2222222222222222, "#7201a8"], [0.3333333333333333, "#9c179e"], [0.4444444444444444, "#bd3786"], [0.5555555555555556, "#d8576b"], [0.6666666666666666, "#ed7953"], [0.7777777777777778, "#fb9f3a"], [0.8888888888888888, "#fdca26"], [1.0, "#f0f921"]]}, "colorway": ["#636efa", "#EF553B", "#00cc96", "#ab63fa", "#FFA15A", "#19d3f3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52"], "font": {"color": "#2a3f5f"}, "geo": {"bgcolor": "white", "lakecolor": "white", "landcolor": "#E5ECF6", "showlakes": true, "showland": true, "subunitcolor": "white"}, "hoverlabel": {"align": "left"}, "hovermode": "closest", "mapbox": {"style": "light"}, "paper_bgcolor": "white", "plot_bgcolor": "#E5ECF6", "polar": {"angularaxis": {"gridcolor": "white", "linecolor": "white", "ticks": ""}, "bgcolor": "#E5ECF6", "radialaxis": {"gridcolor": "white", "linecolor": "white", "ticks": ""}}, "scene": {"xaxis": {"backgroundcolor": "#E5ECF6", "gridcolor": "white", "gridwidth": 2, "linecolor": "white", "showbackground": true, "ticks": "", "zerolinecolor": "white"}, "yaxis": {"backgroundcolor": "#E5ECF6", "gridcolor": "white", "gridwidth": 2, "linecolor": "white", "showbackground": true, "ticks": "", "zerolinecolor": "white"}, "zaxis": {"backgroundcolor": "#E5ECF6", "gridcolor": "white", "gridwidth": 2, "linecolor": "white", "showbackground": true, "ticks": "", "zerolinecolor": "white"}}, "shapedefaults": {"line": {"color": "#2a3f5f"}}, "ternary": {"aaxis": {"gridcolor": "white", "linecolor": "white", "ticks": ""}, "baxis": {"gridcolor": "white", "linecolor": "white", "ticks": ""}, "bgcolor": "#E5ECF6", "caxis": {"gridcolor": "white", "linecolor": "white", "ticks": ""}}, "title": {"x": 0.05}, "xaxis": {"automargin": true, "gridcolor": "white", "linecolor": "white", "ticks": "", "title": {"standoff": 15}, "zerolinecolor": "white", "zerolinewidth": 2}, "yaxis": {"automargin": true, "gridcolor": "white", "linecolor": "white", "ticks": "", "title": {"standoff": 15}, "zerolinecolor": "white", "zerolinewidth": 2}}}},
                        {"responsive": true}
                    ).then(function(){

var gd = document.getElementById('3a6b3126-7240-481c-86ac-38a8ae6ddcdf');
var x = new MutationObserver(function (mutations, observer) {{
        var display = window.getComputedStyle(gd).display;
        if (!display || display === 'none') {{
            console.log([gd, 'removed!']);
            Plotly.purge(gd);
            observer.disconnect();
        }}
}});

// Listen for the removal of the full notebook cells
var notebookContainer = gd.closest('#notebook-container');
if (notebookContainer) {{
    x.observe(notebookContainer, {childList: true});
}}

// Listen for the clearing of the current output cell
var outputEl = gd.closest('.output');
if (outputEl) {{
    x.observe(outputEl, {childList: true});
}}

                        })
                };
                });
            </script>
        </div>

