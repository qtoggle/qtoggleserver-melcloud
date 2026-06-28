## About

This is an addon for [qToggleServer](https://github.com/qtoggle/qtoggleserver).

It provides a driver to control your [MELCloud](https://melcloud.com/) (Mitsubishi Electric) devices with qToggleServer.

This add-on is based on the `python-melcloud` Python package (see https://github.com/erwindouna/python-melcloud). 

Currently only air-to-air units (A/C) are supported.


## Install

Install using pip:

    pip install qtoggleserver-melcloud


## Usage

##### `qtoggleserver.conf:`
``` ini
...
peripherals = [
    ...
    {
        driver = "qtoggleserver.melcloud.MELCloud"
        name = "mymelcloud"                # a name of your choice
        username = "username"
        password = "password"
        # optionally select only specific devices by name
        device_names = ["First Device Name", ...]
    }
    ...
]
...
```
