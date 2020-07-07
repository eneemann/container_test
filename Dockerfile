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
	wget \
	google-cloud-storage
	
RUN apt-get update
RUN apt-get install nano
RUN apt-get install -y git

#Setup File System
RUN mkdir ds
ENV HOME=/ds

WORKDIR /ds

# Sets cache date that can be avoided with an argument
ARG CACHE_DATE=2016-01-01

#Copy data into file system
RUN git clone https://github.com/eneemann/container_test.git /ds

VOLUME /ds

#CMD ["/ds/lidar/add_bldg_heights_container_TEST.py"]
#ENTRYPOINT ["python"]

