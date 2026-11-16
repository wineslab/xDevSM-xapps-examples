# Unified xApp image. One file for every xApp in this repo: pick the xApp with build
# args and the image flavor with --target. See docker/README.md for the full matrix.
#
#   docker build -f docker/Dockerfile --target prod \
#     --build-arg XAPP_DIR=kpm_basic_xapp \
#     --build-arg XAPP_ENTRY=kpm_xapp.py \
#     -t kpm-basic-xapp:prod .
#
# Build context must be the repo root. xDevSM is not a submodule: each xApp installs the
# `xdevsm` package from PyPI through its requirements.txt.

ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim AS deb-fetch

ARG RMR_VERSION=4.9.4
ARG E2AP_VERSION=2.0
ARG E2AP_BRANCH=dev

RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

# O-RAN SC publishes RMR for Debian stretch only; the library runs on newer Debian.
RUN wget -nv --content-disposition https://packagecloud.io/o-ran-sc/release/packages/debian/stretch/rmr_${RMR_VERSION}_amd64.deb/download.deb && \
    wget -nv --content-disposition https://github.com/aferaudo/libe2ap_package/raw/refs/heads/${E2AP_BRANCH}/riclibe2ap_${E2AP_VERSION}_amd64.deb && \
    dpkg -i rmr_${RMR_VERSION}_amd64.deb riclibe2ap_${E2AP_VERSION}_amd64.deb


FROM python:${PYTHON_VERSION}-slim AS base

ARG RMR_VERSION=4.9.4

COPY --from=deb-fetch /usr/local/lib/librmr_si.so.${RMR_VERSION} /usr/local/lib/librmr_si.so
COPY --from=deb-fetch /usr/local/lib/libriclibe2ap.so /usr/local/lib/libriclibe2ap.so
RUN chmod 755 /usr/local/lib/librmr_si.so /usr/local/lib/libriclibe2ap.so

# gcc builds the wheels with no prebuilt binary for this Python (hiredis, pulled in by
# ricsdl). patch applies the ricxappframe patches below.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev patch && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install certifi six python_dateutil setuptools urllib3 logger requests inotify_simple mdclogpy google-api-python-client msgpack ricsdl

# The E2SM libraries bundled in xdevsm need an executable stack: FlexRIC's defer() is a GCC
# nested function, so it runs a trampoline on the stack. Since glibc 2.41 (Debian trixie)
# dlopen refuses such a library unless the process stack is already executable, so the
# interpreter is marked instead of the libraries (clearing their flag makes them crash).
# A running interpreter cannot rewrite itself, hence the copy.
COPY docker/mark_execstack.py /tmp/mark_execstack.py
RUN python="$(readlink -f "$(command -v python3)")" && cp "$python" /tmp/python && \
    python3 /tmp/mark_execstack.py /tmp/python && \
    cp /tmp/python "$python" && rm /tmp/python /tmp/mark_execstack.py

RUN mkdir -p /ws && chmod -R 755 /ws
WORKDIR "/ws"

# Which xApp folder to build and its entry script (see docker/README.md). Declared after
# the common layers: every RUN after an ARG gets it in its environment, so a different
# xApp would otherwise rebuild them all. Without --build-arg XAPP_DIR, the COPY below fails
# naming the missing arg, instead of an empty value copying the whole repo into /ws.
ARG XAPP_DIR=missing-build-arg-XAPP_DIR
ARG XAPP_ENTRY
ARG PLT_NAMESPACE=ricplt-j

COPY ${XAPP_DIR}/requirements.txt /ws/requirements.txt
RUN pip install -r requirements.txt
# Apply the ricxappframe patches xDevSM needs. They ship in the xdevsm package, so they
# version with it, and the build fails if one does not apply (wrong ricxappframe).
RUN python -m xdevsm.ricxappframe_patches
COPY ${XAPP_DIR}/ /ws/

#   --build-arg XAPP_COMMIT=$(git rev-parse HEAD)
ARG XAPP_COMMIT=unknown
RUN printf 'xApp (%s) on commit hash %s\nxdevsm package version %s\n' "${XAPP_DIR}" "${XAPP_COMMIT}" "$(pip show xdevsm | awk '/^Version:/{print $2}')" > /ws/git_commit_info.log

# Unbuffered, so the xApp's Python logs reach `docker/kubectl logs` at once.
ENV PYTHONUNBUFFERED=1
ENV CONFIG_FILE=/ws/config/config-file.json
# xdevsm loads its E2SM libraries package-relative; only RMR and e2ap are system libs.
ENV LD_LIBRARY_PATH=/lib:/usr/lib:/usr/local/lib
ENV PLT_NAMESPACE=${PLT_NAMESPACE}
# So the prod CMD can expand the entry script at runtime.
ENV XAPP_ENTRY=${XAPP_ENTRY}

# This is used to supply a static route table which can be used for debugging,
# testing, or if no route table generator process is being used to supply the route table.
# If not defined, no static table is used and RMR will not report ready until a table is received.
# The static route table may contain both the route table (between newrt start and end records),
# and the MEID map (between meid_map start and end records).
ENV RMR_SEED_RT=./config/uta_rtg.rt


# Automatic start: runs the xApp.
FROM base AS prod
RUN test -n "${XAPP_ENTRY}" || { echo "ERROR: --build-arg XAPP_ENTRY=<entry script> is required for --target prod"; exit 1; }
CMD ["sh", "-c", "exec python ${XAPP_ENTRY}"]


# Manual start: the container idles, so you can exec in and start the xApp yourself
# (python <entry script>).
FROM base AS dev
RUN apt-get update && apt-get install -y --no-install-recommends htop nano procps && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["sleep", "infinity"]
