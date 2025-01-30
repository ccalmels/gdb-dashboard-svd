# gdb-dashboard SVD module

## Description

A [gdb-dashboard](https://github.com/cyrus-and/gdb-dashboard) module to display SVD registers.
![example](gdb-dashboard-svd.png)

Unlike other projects, this one adds the ability to load several SVD files at once. Most of the time, vendors' SVD files does not contain ARM base registers that are usefull for debugging : SCB CFSR for example.

Here's the [Nordic nRF5340 svd file](https://raw.githubusercontent.com/NordicSemiconductor/nrfx/master/mdk/nrf5340_application.svd) and you can see that the System Control Block is not present. To address this, just use the SVD from Nordic and the Cortex-M33 SVD form ARM at the same time.

## Installation

This project depends on [cmsis-svd](https://github.com/cmsis-svd/cmsis-svd) and requires a least gdb-dashboard version 0.17.
```
$ pip3 install -r ./requirements.txt
```

Then simply add gdb-dashboad-svd.py in your ~/.gdbinit.d/ directory.

### Load SVD files
In order to overload the `dashboard svd load` command, you have to define the following environment variable (in your .bashrc for example):
```
export SVD_FOLDER="$HOME/cmsis-svd/data/"
```

Structure of the folder should be `vendor/device.svd`. For example, the nRF5340 SVD file should be in `$HOME/cmsis-svd/data/Nordic/nRF5340.svd`.

You can download a lot of SVD files from [cmsis-svd-data](https://github.com/cmsis-svd/cmsis-svd-data/tree/main/data).

## Usage

All commands benefit from a usefull completion.

### Add some SVD files

```
dashboard svd load ./Cortex-M33.svd ./nrf5340_application.svd
```

### Add some registers to display

```
dashboard svd /_t add SCB CFSR
dashboard svd /a add SCB BFAR
```

The display format depends on the option:
- a for address
- u for decimal
- x for hexadecimal
- t for binary
- _t for binary with separator

### Remove some registers

```
dashboard svd remove SCB CFSR_UFSR_BFSR_MMFSR
dashboard svd remove SCB BFAR
```

### Clear all registers

```
dashboard svd clear
```

## Standalone commmands

This module also creates two gdb commands:
* ```svd info [<peripheral> [<register>]]```
* ```svd get [/auxt_t] <peripheral> <register>```

Example:
```
>>> svd info SCB HFSR
HFSR addr: 0xe000ed2c (access: read-write)
        DEBUGEVT        [31] (DEBUGEVT)
        FORCED  [30] (Forced)
        VECTTBL [1] (VECTTBL)
>>> svd get /_t SCB HFSR
0xe000ed2c:     0b0000_0000_0000_0000_0000_0000_0000_0000
```
