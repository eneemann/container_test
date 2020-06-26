FROM continuumio/miniconda3:latest

##Set environment variables
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN conda install -y -c conda-forge rasterio \
	fiona \
	geopandas \ 
	psycopg2 \
	matplotlib

ENV PATH /opt/conda/bin:$PATH

RUN pip install zipfile36 \
	wget
	
RUN apt-get install nano

#Setup File System
RUN mkdir ds
ENV HOME=/ds
VOLUME /ds
WORKDIR /ds

#Copy data into file system
#COPY ["C:/Users/eneemann/Desktop/GKE Container/",  "./"]
COPY . ./