# gdb-dashboard SVD module

## Description

A [gdb-dashboard](https://github.com/cyrus-and/gdb-dashboard) module to display SVD registers.
![example](gdb-dashboard-svd.png)

## Installation

This project depends on [cmsis-svd](https://pip.pypa.io/en/stable/cli/pip_show/) and requires a least gdb-dashboard version 0.17.
```
$ pip3 install -r ./requirements.txt
```

Then simply add gdb-dashboad-svd.py in your ~/.gdbinit.d/ directory.

## Usage

All commands benefit from a usefull completion.

### Add some SVD files

```
dashboard svd load ./cortex-m4-scb.svd ./nrf5340_application.svd
```

### Add some registers to display

```
dashboard svd add SCB CFSR_UFSR_BFSR_MMFSR
dashboard svd add SCB BFAR
```

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
* ```svd get <peripheral> <register>```
