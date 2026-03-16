# xDevSM-based xApps

This repository contains a set of example xApps built using the xDevSM framework.

## Use xDevSM

Clone the repository and initialize the submodules:
```bash
git clone https://github.com/wineslab/xDevSM-xapps-examples.git

# clone xDevSM code
git submodule init
git submodule update
```

## Build & Deployment workflow
**Note:** The following steps are general, so you can also apply them to build the image of your custom xApp.

1. Clone the repository and initialize submodules.
2. Pick the xApp folder you wish to build.
3. Build the container image using the appropriate Dockerfile in docker.

```bash
docker build --tag <xapp-name>:<version> --file docker/Dockerfile.<xapp_folder> .
```
4. Tag and push the built image to your registry.

```bash
docker tag <xapp-name>:<version> <your_registry>/<xapp-name>:<version>
docker push <your_registry>/<xapp-name>:<version>
```

5. Update the xApp's config file (located inside the xApp folder, e.g., `config/`) so that the container image path (registry/name/tag) matches your pushed image.

```bash
# Example
docker build --tag kpm-basic-xapp:0.2.0-dev --file docker/Dockerfile.kpm_basic_xapp.dev .
docker tag kpm-basic-xapp:0.2.0-dev <your_username>/kpm-basic-xapp:0.2.0-dev
docker push <your_username>/kpm-basic-xapp:0.2.0-dev 
```
```javascript
 // config-file.json
 //...
    "containers": [
        {
            "name": "kpm-basic-xapp",
            "image": {
                "registry": "docker.io",
                "name": "<your_username>/kpm-basic-xapp", // use username
                "tag": "0.2.0-dev"
            }
        }
    ],
```
6. Deploy the xApp via your orchestration or deployment environment using the updated configuration. A guide on how to use OSC-based tools is available [here](https://github.com/aferaudo/ORANInABox/wiki/Deploying-xApp).

## Custom xApp Development

If you wish to develop your own xApp using this framework:

- Use one of the example folders above as a reference starting point.

- Keep the structure: `<name_of_your_xapp>/source_code`, `<name_of_your_xapp>/config_folder`, related Dockerfile in `docker/`.

- Update the container image name, tag, and registration accordingly.

- Follow the build workflow above.

## Contributing
Contributions (bug fixes, enhancements, new example xApps) are welcome.
Please:

1. Fork the repository.
 
2. Develop your change on a branch.

3. Submit a Pull Request.
Make sure to include:

- Clear description of the change

- Any required updates to build steps or documentation

- Documentation and comments where needed

## License
This project is licensed under Apache License Version 2.0 - see [License File](LICENSE) for more details.

## Organizations
| <img src="https://github.com/wineslab.png?s=100" width="60" height="60"> | [**Wireless Networks and Embedded Systems Lab**](https://github.com/wineslab) | [website](https://wineslab.github.io/) |
| :--: | :--: | :--|
| <img src="https://github.com/MMw-Unibo.png?s=100" width="60" height="60"> | [**Mobile Middleware Research Group**](https://github.com/MMw-Unibo) | [website]( https://site.unibo.it/middleware/en) |
