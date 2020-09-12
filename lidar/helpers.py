# -*- coding: utf-8 -*-
"""
Created on Sat Feb 22 11:09:51 2020
@author: Erik

A module to with the following utility functions for the adding building heights
from lidar data:
    - unzip
    - random_points
    - get_height
"""
# from osgeo import gdal
# Import the libraries
import os, sys, time, glob
import geopandas as gpd
import rasterio as rio
import pandas as pd
import numpy as np
from shapely.geometry import Point
import matplotlib.pyplot as plt
import shapely.speedups
import zipfile
from statistics import mean


# Function to unzip files into desired directory
def unzip(directory, file):
    os.chdir = directory
    if file.endswith(".zip"):
        # print(f"Unzipping {file} ...")
        with zipfile.ZipFile(file, "r") as zip_ref:
            zip_ref.extractall(directory)
            

# Create function to sample values at points - input is single-feature GeoDataFrame
def random_points(n, p, poly_df):
#    print(type(poly_df))
#    print(poly_df)
    df = pd.DataFrame(
            {'dsm': [],
             'dtm': [],
             'diff': []})
    pool = p
    # find the bounds of your geodataframe
    x_min, y_min, x_max, y_max = poly_df.total_bounds
    # generate random data within the bounds
    xs = np.random.uniform(x_min, x_max, pool)
    ys= np.random.uniform(y_min, y_max, pool)
    # convert them to a points GeoDataFrame
    poly_points = gpd.GeoDataFrame(df, geometry=[Point(x, y) for x, y in zip(xs, ys)])
   
    # discard points outside of polygon
    # use negative buffer to push selected points to interior of polygon
    # print(float(poly_df.area))
    # buff_size = -2
    
    if float(poly_df.area) < 75:
        buff_size = 0
    elif float(poly_df.area) < 100:
        buff_size = -1
    elif float(poly_df.area) > 2500:
        buff_size = -4
    else:
        buff_size = -2
        
    
    neg_buff = poly_df.geometry.buffer(buff_size)
    sample = poly_points[poly_points.within(neg_buff.unary_union)]
    # sample = poly_points[poly_points.within(poly_df.unary_union)]
    # keep only n points of the random points
    final = sample.head(n + 10)
    # if sample.shape[0] < n:
    #     print(f"Only {sample.shape[0]} sample points available for ADDRESS, X, Y: \
    #                   {poly_df.iloc[0]['address']}, {poly_df.iloc[0].geometry.centroid.x}, {poly_df.iloc[0].geometry.centroid.y}")
    
    return poly_points, final


# Function to add heights as columns in GeoDataFrame - input is single-feature GeoDataFrame
def get_height(row, dsm, dtm, keep, pool):
    full, sample = random_points(keep, pool, row)
    
    # get DSM and DTM values at each sample point
    # open the raster and store metadata
    coords = [(x,y) for x, y in zip(sample.geometry.x, sample.geometry.y)]
    
    with rio.open(dsm) as src:
        sample['dsm'] = [x[0] for x in src.sample(coords)]
        
    with rio.open(dtm) as src:
        sample['dtm'] = [x[0] for x in src.sample(coords)]
    
    sample['diff'] = sample['dsm'] - sample['dtm']
       
    # Keep only points with a height difference > 1 m (avoid points that miss the building)
    sample = sample[sample['diff'] > 1.0 ]
    # Reduce down to number of points in keep variable
    sample = sample.head(keep)
    if sample.shape[0] < 20:
        print(f"Only {sample.shape[0]} sample points used for ADDRESS, X, Y: \
              {row.iloc[0]['address']}, {row.iloc[0].geometry.centroid.x}, {row.iloc[0].geometry.centroid.y}")
    
    # print(sample.to_string())
       
    # Add columns for final estimate fields
    row['BASE_ELEV'] = sample['dtm'].mean()*3.28084
    row['HEIGHT_EST'] = (sample['dsm'].median() - sample['dtm'].mean())*3.28084
    row['HEIGHT_STD'] = np.std(sample['diff'])*3.28084
    row['SAMPLE_PTS'] = sample.shape[0]
    
    # set height estimate to NaN when footprint area is too small
    if float(row.area) < 37:
        row['HEIGHT_EST'] = np.nan
        # print(f"    The area of '{row.iloc[0]['address']}' is too small to reliably estimate building height")

    # fig, ax = plt.subplots(figsize=(14, 7))
    # row.plot(ax=ax, color='lightgray', edgecolor='black')
    # full.plot(ax=ax, color='black', markersize=11, label='All')
    # sample.plot(ax=ax, color='red', markersize=19, label='Used')
    # plt.title(f"{row.iloc[0]['ADDRESS']}, {row.iloc[0]['CITY']}, UT {row.iloc[0]['ZIP5']}")
    # plt.xticks([])
    # plt.yticks([])
    # ax.legend(title='Sample Pts', loc='lower left')
    
    return row
