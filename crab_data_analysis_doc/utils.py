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


def _to_dict(df):
    rows = [list(row) for row in df.collect()]
    ar = np.array(rows)
    tmp_dict = {}
    for i, column in enumerate(df.columns):
        tmp_dict[column] = list(ar[:, i])
    return tmp_dict


def _better_label(index, data):
    labels = []
    for i in range(len(index)):
        percent = data[i]*100/sum(data)
        labels.append(index[i]+": %.3f"%percent+"%")
    return labels


def _other_field(datadict: dict, lessthan: int):
    values_lst = list(datadict.values())
    others = 0
    tmp_dict = {"index": [], "data_percent": [], "other_index": [],"other_percent": []}
    for i in range(len(values_lst[0])):
        percent = float(values_lst[1][i])*100/sum(map(float, values_lst[1]))
        if(percent<lessthan):
            others+=percent
            tmp_dict['other_index'].append(values_lst[0][i])
            tmp_dict['other_percent'].append("%.3f" % percent)
        else:
            tmp_dict['index'].append(values_lst[0][i])
            tmp_dict['data_percent'].append("%.3f" % percent)
    tmp_dict['index'].append("Others")
    tmp_dict['data_percent'].append("%.3f" % others)
    return tmp_dict
    
    
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


def _pie(dictlist: list, figname: str):
    fig, ax = plt.subplots(nrows=1,ncols=len(dictlist), figsize=(10, 10), subplot_kw={'aspect': 'equal'})
    for i in range(len(dictlist)):
        values_lst = list(dictlist[i].values())
        ax[i].pie(values_lst[1], labels=values_lst[0], autopct='%1.1f%%',
            shadow=False, startangle=90)
        ax[i].axis('equal') 
        ax[i].set_title(values_lst[2], fontsize=15)
   
    plt.savefig(figname+".png")
    plt.subplots_adjust(left=0.5,
                        bottom=0.1, 
                        right=2, 
                        top=0.9, 
                        wspace=0.4, 
                        hspace=0.4)
    plt.show()


def _line_graph(xvalues: list, dictlist: list, figinfo: dict, figname: str):
    fig, ax = plt.subplots(figsize=(10, 10))
    
    for i in range(len(dictlist)): 
        values_lst = list(dictlist[i].values())
        ax.plot(xvalues, values_lst[0], color=values_lst[2], label=values_lst[1])
        plt.hlines(mean(values_lst[0]), min(xvalues), max(xvalues), linestyles="dashed", colors=values_lst[2])
        ax.text(mean(xvalues),mean(values_lst[0]),'%f' % (mean(values_lst[0])))

    ax.set(xlabel=figinfo["x_label"], ylabel=figinfo["y_label"],
           title=figinfo["title"])
    ax.grid()
    plt.legend()
    plt.savefig(figname+".png")
    plt.show()


def _table(pandasDataframe):
    plt.figure(figsize=(10, 4))
    ax = plt.subplot() 
    plt.axis('off')
    tbl = table(ax,pandasDataframe, loc='center')
    tbl.auto_set_font_size(True)