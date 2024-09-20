FROM python:3.8-slim as stretch

RUN apt-get update && \
    apt-get install -y \
        wget gcc musl-dev

ARG rmr_version=4.8.0
ARG e2ap_version=1.1.0

# Note: O-RAN-SC only publishes packages for Debian stretch, but stretch does not get official Rust 1.63 updates.
#       Installing this on Debian bullseye seems to work... Should probably request newer packages from O-RAN-SC.
RUN wget -nv --content-disposition https://packagecloud.io/o-ran-sc/release/packages/debian/stretch/rmr_${rmr_version}_amd64.deb/download.deb
RUN wget -nv --content-disposition https://packagecloud.io/o-ran-sc/release/packages/debian/stretch/rmr-dev_${rmr_version}_amd64.deb/download.deb

RUN wget -nv --content-disposition https://packagecloud.io/o-ran-sc/release/packages/debian/stretch/riclibe2ap_${e2ap_version}_amd64.deb/download.deb
RUN wget -nv --content-disposition https://packagecloud.io/o-ran-sc/release/packages/debian/stretch/riclibe2ap-dev_${e2ap_version}_amd64.deb/download.deb

RUN dpkg -i rmr_${rmr_version}_amd64.deb
RUN dpkg -i rmr-dev_${rmr_version}_amd64.deb

RUN dpkg -i riclibe2ap_${e2ap_version}_amd64.deb
RUN dpkg -i riclibe2ap-dev_${e2ap_version}_amd64.deb

RUN ls /usr/local/lib/

FROM python:3.8-slim

ARG rmr_version=4.8.0
ARG e2ap_version=1.1.0

COPY --from=stretch /usr/local/lib/librmr_si.so.${rmr_version} /usr/local/lib/librmr_si.so
COPY --from=stretch /usr/local/lib/libriclibe2ap.so.${e2ap_version} /usr/local/lib/libriclibe2ap.so
COPY ../xapp_framework .
RUN chmod -R 755 /usr/local/lib/librmr_si.so
RUN chmod -R 755 /usr/local/lib/libriclibe2ap.so

# Upgrade pip, install tox
RUN pip install --upgrade pip && pip install certifi six python_dateutil setuptools urllib3 logger requests inotify_simple mdclogpy google-api-python-client msgpack ricsdl
RUN apt update
RUN apt install -y htop nano procps

RUN mkdir -p /ws
RUN chmod -R 755 /ws
WORKDIR "/ws" 

COPY requirements.txt .
COPY . .


# COPY ./sm_py_framework/lib/*.so /usr/local/lib/

RUN pip install -r requirements.txt

ENV CONFIG_FILE=/ws/config/config-file.json
ENV LD_LIBRARY_PATH=/lib:/usr/lib:/usr/local/lib:/ws/xapp_framework/sm_py_framework/lib

# This is used to supply a static route table which can be used for debugging, 
# testing, or if no route table generator process is being used to supply the route table. 
# If not defined, no static table is used and RMR will not report ready until a table is received. 
# The static route table may contain both the route table (between newrt start and end records), 
# and the MEID map (between meid_map start and end records).
ENV RMR_SEED_RT ./config/uta_rtg.rt

# Automatic start
# CMD ["python", "main.py"]

# Manual start
ENTRYPOINT ["sleep", "infinity"]
