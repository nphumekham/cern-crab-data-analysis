import time
from datetime import datetime, date, timedelta

import click
import numpy as np
import pandas as pd
from pandas.plotting import table
from pyspark import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    lit,
    when,
    sum as _sum,
    count as _count,
    first,
    date_format,
    from_unixtime
)
from pyspark.sql.types import (
    StructType,
    LongType,
    StringType,
    StructField,
    DoubleType,
    IntegerType,
)
import matplotlib.pyplot as plt
from matplotlib import cm
from statistics import mean


def _better_label(index, data):
    labels = []
    for i in range(len(index)):
        percent = data[i]*100/sum(data)
        labels.append(index[i]+": %.3f"%percent+"%")
    return labels


def _donut(dictlist: list, figname: str):
    fig, ax = plt.subplots(nrows=1,ncols=len(dictlist), figsize=(10, 10), subplot_kw={'aspect': 'equal'})
    for i in range(len(dictlist)):
        keys_lst = list(dictlist[i].keys())
        values_lst = list(dictlist[i].values())
    
        wedges, texts = ax[i].pie(values_lst[1], wedgeprops={'width': 0.5}, startangle=90)
        ax[i].set_title(values_lst[2], y=1.08, fontsize=15)
        bbox_props = {'boxstyle': 'square,pad=0.3', 'fc': 'w', 'ec': 'k', 'lw': 0.72 }
        kw = {'arrowprops': {'arrowstyle': "-"},
                  'bbox': bbox_props, 'zorder': 0, 'va':"center"}
        for j, p in enumerate(wedges):
            ang = (p.theta2 - p.theta1)/2. + p.theta1
            y = np.sin(np.deg2rad(ang))
            x = np.cos(np.deg2rad(ang))
            horizontalalignment = {-1: "right", 1: "left"}[int(np.sign(x))]
            connectionstyle = "angle,angleA=0,angleB={}".format(ang)
            kw["arrowprops"].update({"connectionstyle": connectionstyle})
            ax[i].annotate(values_lst[0][j], xy=(x, y), xytext=(1.35*np.sign(x), 1.4*y),
                        horizontalalignment=horizontalalignment, **kw)
   
    plt.savefig(figname+".png")
    plt.subplots_adjust(left=0.5,
                        bottom=0.1, 
                        right=2, 
                        top=0.9, 
                        wspace=0.4, 
                        hspace=0.4)
    plt.show()


def _lines_graph(x, data0, data1, xlabel, ylabel, title, **dataLabels):
    fig, ax = plt.subplots(figsize=(10, 10))
    if(dataLabels):
        ax.plot(x, data0, color="blue", label=dataLabels['dataLabel_0'])
        ax.plot(x, data1, color="orange", label=dataLabels['dataLabel_1'])
    else:
        ax.plot(x, data0, color="blue")
        ax.plot(x, data1, color="orange")
    
    plt.hlines(mean(data0), 0,10, linestyles ="dotted", colors ="blue")
    plt.hlines(mean(data1), 0,10, linestyles ="dashed", colors ="orange")
    ax.text(4,mean(data0),'%f' % (mean(data0)))
    ax.text(4,mean(data1),'%f' % (mean(data1)))

    ax.set(xlabel=xlabel, ylabel=ylabel,
           title=title)
    ax.grid()
    plt.legend()
#     plt.savefig('final-avg-cpueff-onsite-offsite.png')
    plt.show()


def _table(pandasDataframe):
    plt.figure(figsize=(10, 4))
    ax = plt.subplot() 
    plt.axis('off')
    tbl = table(ax,pandasDataframe, loc='center')
    tbl.auto_set_font_size(True)