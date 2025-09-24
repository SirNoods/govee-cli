# Govee CLI

A small command-line tool to control **Govee** lights via their official **Cloud API**.
Supports **nicknames** (device aliases) and **groups**

## Features
- Turn on/off, set brightness, color (RGB/HEX), and color temperature
- Nicknames for devices (e.g., `--name lamp`)
- Groups to control multiple devices at once (e.g., `--group livingroom`)
- Simple JSON configs under `~/.config/govee/`

## Quick Start

### 1) Install
Copy the script somewhere on your PATH:
```bash
sudo install -m 0755 govee_cli.py /usr/local/bin/govee