import time
from datetime import datetime, date, timedelta
from exitcode_dict.py import *
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


def _other_fields(index: list, value: list, lessthan: int):
    others = 0
    tmp_dict = {"index": [], "data_percent": [], "other_index": [],"other_percent": []}
    for i in range(len(index)):
        percent = float(value[i])*100/sum(map(float, value))
        if(percent<lessthan):
            others+=percent
            tmp_dict['other_index'].append(index[i])
            tmp_dict['other_percent'].append("%.3f" % percent)
        else:
            tmp_dict['index'].append(index[i])
            tmp_dict['data_percent'].append("%.3f" % percent)
    tmp_dict['index'].append("Others")
    tmp_dict['data_percent'].append("%.3f" % others)
    return tmp_dict
    

def _donut(dictlist: list, figname: str):
    fig, ax = plt.subplots(nrows=1,ncols=len(dictlist), figsize=(10, 10), subplot_kw={'aspect': 'equal'})
    for i in range(len(dictlist)):
        values_lst = list(dictlist[i].values())
        if(len(dictlist)==1):
            wedges, texts = ax.pie(values_lst[1], wedgeprops={'width': 0.5}, startangle=90)
            ax.set_title(values_lst[2], y=1.08, fontsize=15)
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
                ax.annotate(values_lst[0][j], xy=(x, y), xytext=(1.35*np.sign(x), 1.4*y),
                            horizontalalignment=horizontalalignment, **kw)
        else:
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
        if(len(dictlist)==1):
            ax.pie(values_lst[1], labels=values_lst[0], autopct='%1.1f%%',
            shadow=False, startangle=90)
            ax.axis('equal') 
            ax.set_title(values_lst[2], fontsize=15) 
        else:
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


def _line_graph(xvalues: list, dictlist: list, figinfo: dict, figname: str, show_mean: bool):
    fig, ax = plt.subplots(figsize=(10, 10))
    
    for i in range(len(dictlist)): 
        values_lst = list(dictlist[i].values())
        ax.plot(xvalues, values_lst[0], color=values_lst[2], label=values_lst[1])
        if(show_mean):
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
    
def _exitcode_info(exitcode: int):
    exitcode_info = {"ExitCode": exitcode, "Type": "", "Meaning": exitcode_dict.get(str(exitcode), "")}
    
    """ending range plus one as python range exclude the last number"""
    if exitcode in range(1, 512+1):
        exitcode_info['Type'] = "standard ones in Unix and indicate a CMSSW abort that the cmsRun did not catch as exception"
    elif exitcode in range(7000, 9000+1):
        exitcode_info['Type'] = "cmsRun (CMSSW) exit codes. These codes may depend on specific CMSSW version"
    elif exitcode in range(10000, 19999+1):
        exitcode_info['Type'] = "Failures related to the environment setup"
    elif exitcode in range(50000, 59999+1):
        exitcode_info['Type'] = "Failures related executable file"
    elif exitcode in range(60000, 69999+1):
        exitcode_info['Type'] = "Failures related staging-OUT"
    elif exitcode in range(70000, 79999+1):
        exitcode_info['Type'] = "Failures related only for WMAgent."
    elif exitcode in range(80000, 89999+1):
        exitcode_info['Type'] = "Failures related only for CRAB3"
    elif exitcode in range(90000, 99999+1):
        exitcode_info['Type'] = "Other problems which does not fit to any range before"
    
    return exitcode_info


