# -*- coding: utf-8 -*-
"""
Created on Fri Jun 12 15:31:39 2020

@author: eneemann
"""

# import geopandas as gpd
# print('successfully imported geopandas ...')

# import psycopg2
# print('successfully imported psycopg2 ...')

# import wget
# print('successfully imported wget ...')

# import zipfile
# print('successfully imported zipfile ...')

import os, sys, time, glob
import wget
import geopandas as gpd
import rasterio as rio
import pandas as pd
import numpy as np
from shapely.geometry import Point
import matplotlib.pyplot as plt
import shapely.speedups
import zipfile
from statistics import mean
from urllib.error import HTTPError

print('successfully imported all libraries ...')

# Postgres database connection information
con = psycopg2.connect(database="opensgid", user="agrc", password="agrc",
    host="opensgid.agrc.utah.gov")

# Simple query to grab and plot Utah counties
sql = "select * from opensgid.boundaries.county_boundaries"
counties = gpd.GeoDataFrame.from_postgis(sql, con, geom_col='shape')

print(counties.head())