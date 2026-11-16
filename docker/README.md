# Building the xApps

One `docker/Dockerfile` builds every xApp in this repo. Pick the xApp with build args and
the image flavor with `--target`. The build context is the repo root.

## Build args

| Arg | Required | Purpose |
| --- | --- | --- |
| `XAPP_DIR` | yes | xApp folder to build, copied to `/ws` |
| `XAPP_ENTRY` | for `prod` | entry script in that folder |
| `PYTHON_VERSION` | no (`3.11`) | Python of the base image (`xdevsm` needs 3.11) |
| `PLT_NAMESPACE` | no (`ricplt-j`) | RIC platform namespace |
| `XAPP_COMMIT` | no | commit written to `/ws/git_commit_info.log`, with the installed `xdevsm` version |
| `RMR_VERSION`, `E2AP_VERSION`, `E2AP_BRANCH` | no (`4.9.4`, `2.0`, `dev`) | RMR and e2ap libraries |

## Targets

| Target | Behavior |
| --- | --- |
| `prod` | Runs the xApp (`python $XAPP_ENTRY`). |
| `dev` (the default) | Idles (`sleep infinity`), so you can exec in and start the xApp yourself. Adds `htop`, `nano` and `procps`. |

## xApps

| `XAPP_DIR` | `XAPP_ENTRY` |
| --- | --- |
| `kpm_basic_xapp` | `kpm_xapp.py` |
| `kpm_prb_xapp` | `kpm_prb_xapp.py` |
| `prb_control_xapp` | `rc_xapp.py` |
| `radio_bearer_control_xapp` | `rc_xapp.py` |
| `ho_xapp` | `ho_xapp.py` |
| `digital_twin_prb_xapp` | `digital_twin_prb_xapp.py` |
| `traffic_balancer_xapp` | `traffic_balancer.py` |

## Examples

```sh
docker build -f docker/Dockerfile --target prod \
  --build-arg XAPP_DIR=kpm_basic_xapp \
  --build-arg XAPP_ENTRY=kpm_xapp.py \
  --build-arg XAPP_COMMIT=$(git rev-parse HEAD) \
  -t kpm-basic-xapp:0.2.0 .

docker build -f docker/Dockerfile --target dev \
  --build-arg XAPP_DIR=kpm_basic_xapp \
  --build-arg XAPP_ENTRY=kpm_xapp.py \
  -t kpm-basic-xapp:0.2.0-dev .
```

The RMR and e2ap packages are amd64 only: on an arm64 host (e.g. Apple silicon), add
`--platform linux/amd64`.

## What the image does

- Installs RMR and the custom e2ap library (`riclibe2ap`, from
  [aferaudo/libe2ap_package](https://github.com/aferaudo/libe2ap_package)).
- Installs the xApp's `requirements.txt`, which pulls `xdevsm` from PyPI, then applies the
  ricxappframe patches that ship with it (`python -m xdevsm.ricxappframe_patches`).
- Marks the Python interpreter as needing an executable stack (`docker/mark_execstack.py`).
  The E2SM libraries bundled in `xdevsm` need one, and since glibc 2.41 (Debian trixie)
  they do not load otherwise.
