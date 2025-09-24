# Govee CLI

A small, no-frills command-line tool to control **Govee** lights via the official **Cloud API**.
Supports **nicknames** (device aliases) and **groups**, plus one-time migration from an older single-file config.

## Features
- Turn on/off, set brightness, color (RGB/HEX), and color temperature
- Nicknames for devices (e.g., `--name lamp`)
- Groups to control multiple devices at once (e.g., `--group livingroom`)
- Simple JSON configs under `~/.config/govee/`
- Optional migration from `~/.config/govee_devices.json` to the new two-file layout

## Quick Start

### 1) Install
Copy the script somewhere on your PATH:
```bash
sudo install -m 0755 govee_cli.py /usr/local/bin/govee