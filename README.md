
# Govee CLI

A small command-line tool to control Govee lights via their official Cloud API. Supports nicknames (device aliases) and groups.

## Features

- Turn on/off, set brightness, color (RGB/HEX) and color temperature
- Nicknames for devices
- Groups to control multiple devices at once
- Simple JSON configs under `~/.config/govee/`




## Installation

Just clone the repo or download the script and run it with Python:
```
git clone https://github.com/SirNoods/govee-cli.git
cd govee-cli
python3 govee_cli.py --help
```

## API Key
This CLI requires a Govee developer API key.
You can generate one by logging into the [Govee Developer Console](https://developer.govee.com/).
Once you have it, export it as an environment variable before running commands.

```
export GOVEE_API_KEY="your-api-key-here"
```


## Usage / Examples

Once your API key and configuration are set up, you can control your devices from the terminal.

### List devices
Shows all devices on your account, including any nicknames you’ve configured.
```bash
python3 govee_cli.py list
```

### Power
Turn a device or group on/off.
```
# By nickname
python3 govee_cli.py power on --name lamp
python3 govee_cli.py power off -n desk

# By group
python3 govee_cli.py power off --group livingroom
python3 govee_cli.py power on -g stream
```

### Brightness
Set brightness from 0-100.
```
python3 govee_cli.py brightness 75 -n lamp
python3 govee_cli.py brightness 40 -g livingroom
```

### Color
Set color either by hex code or RGB values.
```
# Hex color
python3 govee_cli.py color --hex "#ffaa00" -n lamp

# RGB values
python3 govee_cli.py color --rgb 0 128 255 -g stream
```

## Configuration

The script looks for config files in `~/.config/govee/` and will create them when using the name or group features.

### Devices (nicknames)

Create a `devices.json` file to give your lights short, memorable names:

`~/.config/govee/devices.json`
```json
{
  "lamp": { "id": "AA:BB:CC:DD:EE:FF:11:22", "model": "H6008" },
  "desk": { "id": "11:22:33:44:55:66:77:88", "model": "H6008" }
}
```
Each key is your chosen nickname.
Each entry must include both the id and model (found with `govee list).

### Groups
Groups let you control multiple devices at once.
`~/.config/govee/groups.json`

```
{
  "livingroom": ["lamp", "desk"],
  "stream": ["lamp", { "id": "11:22:33:44:55:66:77:88", "model": "H6008" }]
}
```

Members can be nicknames (strings from devices.json) or inline (id, model).


You can manage these files manually, or use the built-in commands:
```
# Devices
python3 govee_cli.py names list
python3 govee_cli.py names add lamp -d <DEVICE_ID> -m H6008
python3 govee_cli.py names remove lamp

# Groups
python3 govee_cli.py groups add livingroom
python3 govee_cli.py groups add-members livingroom --names lamp desk
python3 govee_cli.py groups list
python3 govee_cli.py groups show livingroom


```
## License

Project licensed under the [MIT License](https://choosealicense.com/licenses/mit/)

