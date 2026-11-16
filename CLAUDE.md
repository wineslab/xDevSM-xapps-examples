# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A collection of **example xApps** built on the **xDevSM** framework. xDevSM is the actual SDK,
now distributed as the [`xdevsm`](https://pypi.org/project/xdevsm/) **PyPI package** (it used to be
a git submodule at `xDevSM/`); the top-level folders are reference applications that consume it.

Install it (and the rest of an xApp's deps) from that xApp's `requirements.txt`:

```bash
cd <xapp-folder> && pip install -r requirements.txt   # pulls in xdevsm from PyPI
```

> The framework targets the **O-RAN Software Community (OSC) Near-RT RIC, Release J** exclusively. It will not run against other RIC implementations.

## Architecture

xDevSM has three layers; understanding the boundary between them is the key to working here.

1. **xApp API layer** (`xdevsm/handlers/`) — `BasexDevSMXapp` (abstract contract: `send`/`handle`/`terminate`/`get_ran_function_description`) and `xDevSMRMRXapp`, which fuses OSC's `ricxappframe.RMRXapp` with that contract. `xDevSMRMRXapp` is the spine of every xApp: it stands up RMR ports + routing table, the threaded HTTP server with `/ric/v1/config|health/alive|health/ready`, namespaces, and the E2 Manager link used to discover connected gNBs.

2. **Service Model wrappers / "decorators"** (`xdevsm/decorators/`) — developer-facing APIs, attached by **composition, not subclassing**:
   - `BaseXDevSMWrapper` → `xAppReportService` → `XappKpmFrame` (KPM subscribe/indication decode, in `decorators/kpm/`)
   - `BaseXDevSMWrapper` → `xAppControlService` → `RadioBearerControl` / `RadioResourceAllocationControl` / `ConnectedModeMobilityControl` (RC control requests + ACK/failure handling, in `decorators/rc/`)

3. **sm_framework** (`xdevsm/sm_framework/`) — the encode/decode engine. `py_oran/` holds ctypes mappings to native `.so` libraries bundled in `xdevsm/sm_framework/lib/` (`libkpm_sm*.so`, `librc_1_03.so`, `libsm_framework.so`, `libdapp_sm.so`), loaded package-relative at import. Because everything crosses into C, most encode/decode functions take or return a `ByteArray` (an `int8[]` + length) — it is plumbing, not an architectural hub, despite appearing ubiquitous.

### The wiring pattern every xApp follows

```python
from xdevsm.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp
from xdevsm.decorators.kpm.kpm_frame import XappKpmFrame

xapp_gen = xDevSMRMRXapp("0.0.0.0", route_file=args.route_file)  # the spine
kpm_api  = XappKpmFrame(xapp_gen, ...)     # wrap with a Service Model decorator
xapp_gen.register_shutdown(cleanup_fn)     # optional cleanup (e.g. InfluxDB close)
xapp_gen.register_handler(my_handler)      # inject the indication/control handler
xapp_gen.run()                             # hand control to the RMR event loop
```

Incoming RMR messages flow through `xDevSMRMRXapp._dispatch_event` → the registered handler (or `handle()` fallback). RC control parameters are adjusted via getter/setter methods on the control wrapper.

xApps import the framework as the installed `xdevsm` package (`from xdevsm.* import …`) — no `sys.path` bootstrap is needed anymore (the old `setup_imports.py` shims were removed when xDevSM moved from a submodule to a PyPI dependency).

## Per-xApp layout convention

Each `*_xapp/` folder is self-contained and follows the same shape (keep it for new xApps):

```
<xapp>/
  <main>.py            # entrypoint (kpm_xapp.py, rc_xapp.py, ho_xapp.py, digital_twin_prb_xapp.py)
  requirements.txt     # per-xApp deps (includes xdevsm)
  config/
    config-file.json   # xApp descriptor (container image, ports, messaging)
    schema.json        # JSON schema validating config-file.json
    uta_rtg.rt         # static RMR route table (RMR_SEED_RT)
```

Application-specific behaviour lives in container classes inside the main file (`DataManager`, `xAppMonControlContainer`, `PRBCotrolXAppDataManager`), which compose a `xDevSMRMRXapp` instance rather than extending it.

## Build & run

There is **no test suite, linter, or build script** — these are container-deployed xApps. The workflow is Docker-based, one `docker/Dockerfile` for every xApp, picked with build args (`docker/README.md` lists the args, targets and xApps):

```bash
# Build (run from repo root — the build context copies the xApp folder; xdevsm is pip-installed)
docker build --file docker/Dockerfile --target prod \
  --build-arg XAPP_DIR=<xapp_folder> --build-arg XAPP_ENTRY=<main>.py \
  --tag <xapp-name>:<version> .

# Example
docker build --file docker/Dockerfile --target dev \
  --build-arg XAPP_DIR=kpm_basic_xapp --build-arg XAPP_ENTRY=kpm_xapp.py \
  --tag kpm-basic-xapp:0.2.0-dev .
docker tag kpm-basic-xapp:0.2.0-dev <registry>/kpm-basic-xapp:0.2.0-dev
docker push <registry>/kpm-basic-xapp:0.2.0-dev
```

Then update `containers[].image` in that xApp's `config/config-file.json` to match the pushed image, and deploy via the RIC (OSC deployment guide: https://github.com/aferaudo/ORANInABox/wiki/Deploying-xApp).

**The `dev` target uses `ENTRYPOINT ["sleep", "infinity"]`** — the container starts idle so you can exec in and launch manually for debugging:

```bash
python <main>.py [args]   # e.g. python kpm_xapp.py -r ./config/uta_rtg.rt
```

The `prod` target runs the xApp (`python $XAPP_ENTRY`).

### Things the Dockerfile does that matter

- Install OSC native libs from packagecloud: **RMR 4.9.4** and a **custom e2ap 2.0** (`riclibe2ap`, from `github.com/aferaudo/libe2ap_package`). These `.so`s are required at runtime.
- Apply the ricxappframe patches that ship with `xdevsm` (`python -m xdevsm.ricxappframe_patches`): they re-enable the indication-message free, add the RIC Control Acknowledge/Failure decoders, and size the control request buffer to the message.
- The SM `.so`s ship inside the pip-installed `xdevsm` package and load package-relative, so `LD_LIBRARY_PATH` no longer needs an xDevSM entry (only the RMR/e2ap system libs). They need an executable stack (FlexRIC's `defer()` runs a trampoline on it), which glibc ≥ 2.41 refuses at `dlopen`, so the image (`python:3.11-slim`, Debian trixie) marks the Python interpreter instead (`docker/mark_execstack.py`). Never clear the flag on the libraries: they crash.
- Key env vars: `CONFIG_FILE`, `RMR_SEED_RT` (static route table), `PLT_NAMESPACE` (RIC platform namespace).

## The digital_twin_prb_xapp (most complex example)

An evolution of `kpm_prb_xapp` that manages **per-slice PRB allocation on a real gNB plus its digital twin (DT)**. Control flow worth knowing before editing it: every PRB-quota change is **first validated on the DT** and only replayed on the real gNB after the DT returns `RIC_CONTROL_ACK` (on `RIC_CONTROL_FAILURE` the real gNB is left untouched). At most one control is in flight per gNB, correlated by `meid` ("option-A"), with per-(gNB, slice) FIFO queues and ACK-timeout retries.
