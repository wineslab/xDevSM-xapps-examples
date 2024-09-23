# xDevSM-xapps-examples

Repository gathering xApps that utilize the xDevSM framework.

## Building the xApp Image

Clone the repository and initialize the submodules:
```bash
git clone https://github.com/wineslab/xDevSM-xapps-examples.git

# clone xDevSM code
git submodule init
git submodule update
```

**Note:** The following steps are general, so you can also apply them to build the image of your custom xApp.

Build the Image of the xApp:
```bash
docker build --tag kpm-basic-xapp:0.1.0 --file docker/Dockerfile.kpm_basic_xapp .
```

Push the Image to a Repository:
```bash
docker tag kpm-basic-xapp:0.1.0 <your_username>/kpm-basic-xapp:0.1.0
docker push <your_username>/kpm-basic-xapp:0.1.0
```

Change the xApp config file (**xapps-repo → kpm_basic_xapp → config**):
```json
 // config-file.json
 //...
    "containers": [
        {
            "name": "kpm-basic-xapp",
            "image": {
                "registry": "docker.io",
                "name": "<your_username>/kpm-basic-xapp", // use username
                "tag": "0.1.0"
            }
        }
    ],
```

## License
This project is licensed under Apache License Version 2.0 - see [License File](LICENSE) for more details.

## Organizations
| <img src="https://github.com/wineslab.png?s=100" width="60" height="60"> | [**Wireless Networks and Embedded Systems Lab**](https://github.com/wineslab) | [website](https://ece.northeastern.edu/wineslab/index.php) |
| :--: | :--: | :--|
| <img src="https://github.com/MMw-Unibo.png?s=100" width="60" height="60"> | [**Mobile Middleware Research Group**](https://github.com/MMw-Unibo) | [website]( https://site.unibo.it/middleware/en) |
