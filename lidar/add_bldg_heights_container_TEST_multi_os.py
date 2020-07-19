# -*- coding: utf-8 -*-
"""
Created on Sat Feb 22 11:09:51 2020
@author: Erik

EMN: Script to add heights to building footprints
"""
# from osgeo import gdal
# Import the libraries
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
from tqdm import tqdm
from google.cloud import storage
import multiprocessing

# Start timer and print start time in UTC
start_time = time.time()
readable_start = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
print("The script start time is {}".format(readable_start))

today = time.strftime("%Y%m%d")

# Set up environment and point to the right projection files
# os.environ["PROJ_LIB"] = r"C:\Users\eneemann\AppData\Local\ESRI\conda\envs\erik_test\Library\share"
# Apparent location for container install:
os.environ["PROJ_LIB"] = r"/opt/conda/share"
shapely.speedups.enable()     # Speed up shapely operations
pd.options.mode.chained_assignment = None     # Turn off SettingWithCopyWarning

# Initialize google cloud storage client
client_storage = storage.Client()
out = 'container_test'
out_bucket = client_storage.get_bucket(out)

# Set variables to use later in the code
work_dir = r'/ds/lidar'
os.chdir = work_dir
dsm_gcp_path = r'https://storage.googleapis.com/state-of-utah-sgid-downloads/lidar/wasatch-front-2013-2014/DSMs/'
dsm_tiles = 'LiDAR2013_2014_50cm_SLCounty_DSM_Tiles.shp'
dtm_gcp_path = r'https://storage.googleapis.com/state-of-utah-sgid-downloads/lidar/wasatch-front-2013-2014/DTMs/'
dtm_tiles = 'LiDAR2013_2014_50cm_SLCounty_DTM_Tiles.shp'
bldg_footprints = 'SLCounty_footprints_small_new.shp'
out_name = 'SLC_small_TEST_footprints_' + today

# Create DSM and DTM directories
dsm_dir = os.path.join(work_dir, 'DSM')
dtm_dir = os.path.join(work_dir, 'DTM')
if os.path.isdir(dsm_dir) == False:
    os.mkdir(dsm_dir)
if os.path.isdir(dtm_dir) == False:
    os.mkdir(dtm_dir)

###############
#  Functions  #
###############

# Function to unzip files into desired directory
def unzip(directory, file):
    os.chdir = directory
    if file.endswith(".zip"):
        # print(f"Unzipping {file} ...")
        with zipfile.ZipFile(file, "r") as zip_ref:
            zip_ref.extractall(directory)
            

# Create function to sample values at points - input is single-feature GeoDataFrame
def random_points(n, poly_df):
#    print(type(poly_df))
#    print(poly_df)
    df = pd.DataFrame(
            {'dsm': [],
             'dtm': [],
             'diff': []})
    pool = 100
    # find the bounds of your geodataframe
    x_min, y_min, x_max, y_max = poly_df.total_bounds
    # generate random data within the bounds
    xs = np.random.uniform(x_min, x_max, pool)
    ys= np.random.uniform(y_min, y_max, pool)
    # convert them to a points GeoDataFrame
    poly_points = gpd.GeoDataFrame(df, geometry=[Point(x, y) for x, y in zip(xs, ys)])
    # discard points outside of polygon
    sample = poly_points[poly_points.within(poly_df.unary_union)]
    # keep only 25 points of the random points
    final = sample.head(n)
    if sample.shape[0] < 25:
        print(f'Only {sample.shape[0]} sample points available for address, X, Y: \
                      {poly_df.address, poly_df.geometry.centroid.x, poly_df.geometry.centroid.y}')
    
    return final


# Function to add heights as columns in GeoDataFrame - input is single-feature GeoDataFrame
def get_height(row, dsm_f, dtm_f):
    sample = random_points(25, row)
    
    # get DSM and DTM values at each sample point
    # open the raster and store metadata
    coords = [(x,y) for x, y in zip(sample.geometry.x, sample.geometry.y)]
    
    with rio.open(dsm_f) as src:
        sample['dsm'] = [x[0] for x in src.sample(coords)]
        
    with rio.open(dtm_f) as src:
        sample['dtm'] = [x[0] for x in src.sample(coords)]
    
    sample['diff'] = sample['dsm'] - sample['dtm']    
    
    # add columns for average DSM and DTM values, difference field
    row['dsm'] = sample['dsm'].mean()
    row['dtm'] = sample['dtm'].mean()
    row['diff'] = sample['diff'].mean()
    row['height_ft'] = row['diff']*3.28084
    
    return row


# Read in lidar index tile and building footprints shapefiles
dsm_index = gpd.read_file(os.path.join(work_dir, dsm_tiles))
dtm_index = gpd.read_file(os.path.join(work_dir, dtm_tiles))
footprints = gpd.read_file(os.path.join(work_dir, bldg_footprints))
# First transform footprints into UTM 12N (26912) - units are meters
#footprints = footprints.to_crs(epsg=26912)
#footprints = footprints.to_crs(dsm_index.crs)
# print(footprints.crs)
# print(dsm_index.crs)

county_list = ['SALT LAKE']
footprints_SL = footprints[footprints['county'].isin(county_list)]

#ax = subset.plot(figsize=(10, 6),
#    color='white', edgecolor='black')
#plt.show()

keep_cols = ['name', 'type', 'address', 'city', 'zip5', 'county',
             'fips', 'parcel_id', 'src_year', 'geometry', 'dsm', 'dtm', 'diff', 'height_ft']

# Initialize all_footprints as None and tile_times as empty list
# all_footprints = None
# tile_times = []


def multi_func(x):
    global tile_times
    tile_times = []
    section_time = time.time()
    row = dsm_index.iloc[[x]]
    tile_base = row['TILE'][x]
    print(f'Working on tile {tile_base} ...')
    
    # Intersect tile and footprints to determine if any need processed
    tile = dsm_index[dsm_index['TILE'] == tile_base]
    subset = gpd.overlay(tile, footprints_SL, how='intersection')
    
    if subset.shape[0] != 0:
        
        # Create DSM and DTM download and local file paths
        dsm_path = dsm_gcp_path + str(tile_base) + '.zip'
        dsm_file = os.path.join(dsm_dir, str(tile_base) + '.img')
        dsm_zip = os.path.join(dsm_dir, str(tile_base) + '.zip')
        dtm_path = dtm_gcp_path + str(tile_base) + '.zip'
        dtm_path = dtm_path.replace('hh', 'bh')
        dtm_file = os.path.join(dtm_dir, str(tile_base) + '.img')
        dtm_file = dtm_file.replace('hh', 'bh')
        
        # Select a tile and download DSM and DTM from google cloud storage
        
        if not os.path.isfile(dsm_zip):
            try:
                dsm = wget.download(dsm_path, dsm_dir)
            except HTTPError:
                print('Encountered HTTPError, skipping to next tile ...')
                return
        else:
            dsm = dsm_zip
            print(f'{dsm} already exists ...')
        
        try:
            dtm = wget.download(dtm_path, dtm_dir)
        except HTTPError:
            print('Encountered HTTPError, skipping to next tile ...')
            return
        
        print(f'Downloaded {dsm} and {dtm} ...')
        
        # Unzip DSM and DTM
        unzip(dsm_dir, dsm)
        unzip(dtm_dir, dtm)
        
        # Iterate over footprints in the tile    
        for j in np.arange(subset.shape[0]):
            temp = subset.iloc[[j]]
            updated = get_height(temp, dsm_file, dtm_file)
            if j == 0:
                subset_final = updated
            else:
                subset_final = subset_final.append(updated, ignore_index=True)
            
        # Delete DSM and DTM files, zipped files, and all .xmls
        os.remove(dsm_file)
        os.remove(dsm)
        os.remove(dtm_file)
        os.remove(dtm)
        for item in os.listdir(dsm_dir):
            if item.endswith(".xml"):
                os.remove(os.path.join(dsm_dir, item))
        for item in os.listdir(dtm_dir):
            if item.endswith(".xml"):
                os.remove(os.path.join(dtm_dir, item))
        
        # print("Time elapsed for tile subset: {:.2f}s".format(time.time() - section_time))
        tile_times.append(time.time() - section_time)
        
        section_time = time.time()
        
        subset_final = subset_final[keep_cols]
        # subset_final = subset_final.to_crs(epsg=26912)
    
        # if x == 0 or all_footprints is None:
        #     all_footprints = subset_final
        # else:
        #     all_footprints = all_footprints.append(subset_final, ignore_index=True)
            
        return subset_final
    
        del updated
        del subset_final
        
    else:
        del subset
        print('    No overlapping footprints in tile, moving on ...')
    
    
# Iterate over all rows in tile index
# for i in tqdm(np.arange(dsm_index.shape[0])):
# for i in np.arange(1):

pool = multiprocessing.Pool(processes=None)  # use all available cores
results = pool.map(multi_func, tqdm(np.arange(dsm_index.shape[0])))
all_footprints = pd.concat(results)
pool.close()

# Export footprints with new data to shapefile
#out_file = os.path.join(work_dir, 'footprints_' + tile_base + '.shp')
out_file = os.path.join(work_dir, out_name + '.shp')
all_footprints.to_file(driver = 'ESRI Shapefile', filename=out_file)

# # Upload to google cloud storage
# out_gcs = out_name + '.shp'
# new_blob = out_bucket.blob(out_gcs)
# new_blob.upload_from_filename(out_file)
# print(f'{out_gcs} uploaded to: gs://{out_bucket}/{out_name}')

# Upload all shapefile components to google cloud storage
def upload_files(directory, bucket):
    for file in os.listdir(directory):
        if out_name in file:
            new_blob = bucket.blob(file)
            new_blob.upload_from_filename(os.path.join(work_dir, file))
            print(f'{file} uploaded to: gs://{bucket}/{file}')


upload_files(work_dir, out_bucket)

# print(f"Average time per tile index (in seconds): {mean(tile_times)}")

print("Script shutting down ...")
# Stop timer and print end time in UTC
readable_end = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
print("The script end time is {}".format(readable_end))
print("Time elapsed: {:.2f}s".format(time.time() - start_time))

