"""
govee_cli.py — Control Govee lights via the official Cloud API.

Nicknames + Groups
------------------
Config file: ~/.config/govee_devices.json

Devices (nicknames) are top-level keys mapping to {"id","model"}.
Groups live under a special "_groups" key and contain lists of members.
Members can be nickname strings or inline {"id","model"} objects.

Example:
{
  "lamp": {"id": "aa:bb:...:11:22", "model": "H6008"},
  "desk": {"id": "11:22:...:77:88", "model": "H6008"},
  "_groups": {
    "livingroom": ["lamp", "desk"],
    "stream": ["lamp", {"id":"11:22:...:77:88","model":"H6008"}]
  }
}

Usage examples:
  export GOVEE_API_KEY="YOUR_API_KEY"

  # List devices (shows nicknames)
  python3 govee_cli.py list

  # Use a nickname
  python3 govee_cli.py power on --name lamp

  # Use a group (applies to all members)
  python3 govee_cli.py power off --group livingroom
  python3 govee_cli.py brightness 40 --group stream
  python3 govee_cli.py color --hex #ffaa00 --group livingroom

  # Manage nicknames
  python3 govee_cli.py names list
  python3 govee_cli.py names add lamp -d <DEVICE_ID> -m H6008
  python3 govee_cli.py names remove lamp

  # Manage groups
  python3 govee_cli.py groups list
  python3 govee_cli.py groups show livingroom
  python3 govee_cli.py groups add livingroom
  python3 govee_cli.py groups add-members livingroom --names lamp desk
  python3 govee_cli.py groups add-members livingroom --pairs id1:model1 id2:model2
  python3 govee_cli.py groups remove-members livingroom --names lamp
  python3 govee_cli.py groups remove livingroom
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, Any, Optional, Tuple, List

import urllib.request

API_BASE = "https://developer-api.govee.com/v1"
API_KEY_ENV = "GOVEE_API_KEY"
CONFIG_PATH = os.path.expanduser("~/.config/govee_devices.json")
GROUPS_KEY = "_groups"


class GoveeError(Exception):
    pass


def api_request(path: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        raise GoveeError(f"Missing API key. Set the {API_KEY_ENV} environment variable.")
    url = f"{API_BASE}{path}"
    req_headers = {
        "Govee-API-Key": api_key,
        "Content-Type": "application/json",
    }
    if headers:
        req_headers.update(headers)

    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_data = resp.read()
            try:
                return json.loads(resp_data.decode("utf-8"))
            except json.JSONDecodeError:
                raise GoveeError(f"Invalid JSON response: {resp_data!r}")
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8")
        except Exception:
            msg = str(e)
        raise GoveeError(f"HTTP {e.code}: {msg}") from e
    except urllib.error.URLError as e:
        raise GoveeError(f"Network error: {e}") from e


def list_devices() -> Dict[str, Any]:
    return api_request("/devices")


def _load_raw_config() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise GoveeError(f"Config JSON is invalid at {CONFIG_PATH}: {e}")


def load_config_devices() -> Dict[str, Dict[str, str]]:
    data = _load_raw_config()
    out = {}
    for k, v in data.items():
        if k == GROUPS_KEY:
            continue
        if isinstance(v, dict) and "id" in v and "model" in v:
            out[str(k)] = {"id": str(v["id"]), "model": str(v["model"])}
    return out


def load_config_groups() -> Dict[str, List[Any]]:
    data = _load_raw_config()
    groups = data.get(GROUPS_KEY, {})
    if not isinstance(groups, dict):
        raise GoveeError(f"{CONFIG_PATH} has invalid '{GROUPS_KEY}' format. Expected an object.")
    return groups


def save_full_config(devmap: Dict[str, Dict[str, str]], groups: Dict[str, List[Any]]) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    payload = dict(sorted(devmap.items()))
    payload[GROUPS_KEY] = groups
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_path, CONFIG_PATH)


def guess_single_h6008(devices: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    items = devices.get("data", devices).get("devices", [])
    h6008 = [d for d in items if d.get("model") == "H6008"]
    if len(h6008) == 1:
        return h6008[0].get("device"), h6008[0].get("model", "H6008")
    return None


def resolve_single_target(name: Optional[str], device: Optional[str], model: Optional[str]) -> Tuple[str, str]:
    if name:
        devmap = load_config_devices()
        ent = devmap.get(name)
        if not ent:
            raise GoveeError(f"Nickname '{name}' not found in {CONFIG_PATH}. Use `names add` to create it.")
        return ent["id"], ent["model"]
    if device and model:
        return device, model
    devices = list_devices()
    guessed = guess_single_h6008(devices)
    if guessed:
        dev, mdl = guessed
        print(f"[info] Using detected H6008 device: {dev} ({mdl})")
        return dev, mdl
    raise GoveeError("Specify --name OR --device and --model, or have exactly one H6008 on the account.")


def resolve_targets(name: Optional[str], device: Optional[str], model: Optional[str], group: Optional[str]) -> List[Tuple[str, str]]:
    """Return list of (device, model)."""
    if sum(bool(x) for x in (name, group)) > 1:
        raise GoveeError("Use only one of --name or --group (or explicit --device/--model).")
    if group:
        devmap = load_config_devices()
        groups = load_config_groups()
        members = groups.get(group)
        if members is None:
            raise GoveeError(f"Group '{group}' not found. Create it with `groups add {group}` and add members.")
        resolved: List[Tuple[str, str]] = []
        for m in members:
            if isinstance(m, str):
                if m not in devmap:
                    raise GoveeError(f"Group '{group}' refers to unknown nickname '{m}'. Add it with `names add`.")
                ent = devmap[m]
                resolved.append((ent["id"], ent["model"]))
            elif isinstance(m, dict) and "id" in m and "model" in m:
                resolved.append((str(m["id"]), str(m["model"])))
            else:
                raise GoveeError(f"Invalid member in group '{group}': {m!r}")
        if not resolved:
            raise GoveeError(f"Group '{group}' has no members.")
        return resolved
    # single target path
    dev, mdl = resolve_single_target(name, device, model)
    return [(dev, mdl)]


def control(device: str, model: str, cmd: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "device": device,
        "model": model,
        "cmd": cmd
    }
    return api_request("/devices/control", method="PUT", data=payload)


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.strip().lower()
    if h.startswith("#"):
        h = h[1:]
    if not re.fullmatch(r"[0-9a-f]{6}", h):
        raise GoveeError("HEX color must look like #RRGGBB (e.g., #ff8800).")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return r, g, b


def cmd_list(_args: argparse.Namespace) -> None:
    devmap = load_config_devices()
    data = list_devices()
    devices = data.get("data", data).get("devices", [])
    if not devices:
        print("No devices found.")
        return

    id_to_names = {}
    for nick, ent in devmap.items():
        id_to_names.setdefault(ent["id"], []).append(nick)

    for d in devices:
        dev_id = d.get("device")
        model = d.get("model")
        names = ", ".join(sorted(id_to_names.get(dev_id, []))) or "-"
        print(f"- {d.get('deviceName','(unnamed)')} — id={dev_id} model={model} controllable={d.get('controllable')} retrievable={d.get('retrievable')} nicknames=[{names}]")


def _apply_to_targets(targets: List[Tuple[str, str]], cmd: Dict[str, Any]) -> None:
    # Apply command to each target; print a compact result line per device.
    for dev, mdl in targets:
        try:
            resp = control(dev, mdl, cmd)
            print(json.dumps({"device": dev, "model": mdl, "result": resp}, indent=2))
        except GoveeError as e:
            print(json.dumps({"device": dev, "model": mdl, "error": str(e)}))


def cmd_power(args: argparse.Namespace) -> None:
    targets = resolve_targets(args.name, args.device, args.model, args.group)
    value = "on" if args.state.lower() == "on" else "off"
    _apply_to_targets(targets, {"name": "turn", "value": value})


def cmd_brightness(args: argparse.Namespace) -> None:
    targets = resolve_targets(args.name, args.device, args.model, args.group)
    value = clamp(int(args.level), 0, 100)
    _apply_to_targets(targets, {"name": "brightness", "value": value})


def cmd_color(args: argparse.Namespace) -> None:
    targets = resolve_targets(args.name, args.device, args.model, args.group)
    if args.hex:
        r, g, b = hex_to_rgb(args.hex)
    elif args.rgb:
        r, g, b = (clamp(int(args.rgb[0]), 0, 255),
                   clamp(int(args.rgb[1]), 0, 255),
                   clamp(int(args.rgb[2]), 0, 255))
    else:
        raise GoveeError("Provide either --hex or --rgb R G B.")
    _apply_to_targets(targets, {"name": "color", "value": {"r": r, "g": g, "b": b}})


def cmd_cct(args: argparse.Namespace) -> None:
    targets = resolve_targets(args.name, args.device, args.model, args.group)
    kelvin = clamp(int(args.kelvin), 2000, 9000)
    _apply_to_targets(targets, {"name": "colorTem", "value": kelvin})


# ---- Names (nicknames) management ----
def _load_merged() -> Dict[str, Any]:
    devmap = load_config_devices()
    groups = load_config_groups()
    merged = dict(sorted(devmap.items()))
    merged[GROUPS_KEY] = groups
    return merged


def names_list(_args: argparse.Namespace) -> None:
    devmap = load_config_devices()
    if not devmap:
        print(f"(no nicknames) — create one with: govee_cli.py names add <nick> -d <id> -m <model>")
        return
    for nick, ent in sorted(devmap.items()):
        print(f"{nick}: id={ent['id']} model={ent['model']}")


def names_add(args: argparse.Namespace) -> None:
    devmap = load_config_devices()
    groups = load_config_groups()
    nick = args.nickname
    devmap[nick] = {"id": args.device, "model": args.model}
    save_full_config(devmap, groups)
    print(f"Saved nickname '{nick}' -> id={args.device} model={args.model} in {CONFIG_PATH}")


def names_remove(args: argparse.Namespace) -> None:
    devmap = load_config_devices()
    groups = load_config_groups()
    nick = args.nickname
    if nick not in devmap:
        print(f"Nickname '{nick}' not found in {CONFIG_PATH}")
        return
    del devmap[nick]
    # Remove from all groups
    for g, members in list(groups.items()):
        groups[g] = [m for m in members if not (isinstance(m, str) and m == nick)]
    save_full_config(devmap, groups)
    print(f"Removed nickname '{nick}' from {CONFIG_PATH} and all groups")


# ---- Groups management ----
def groups_list(_args: argparse.Namespace) -> None:
    groups = load_config_groups()
    if not groups:
        print("(no groups) — create one with: govee_cli.py groups add <group>")
        return
    for g, members in sorted(groups.items()):
        ms = []
        for m in members:
            if isinstance(m, str):
                ms.append(m)
            elif isinstance(m, dict):
                ms.append(f"{m.get('id')}:{m.get('model')}")
        print(f"{g}: [{', '.join(ms)}]")


def groups_show(args: argparse.Namespace) -> None:
    groups = load_config_groups()
    members = groups.get(args.group)
    if members is None:
        print(f"Group '{args.group}' not found.")
        return
    ms = []
    for m in members:
        if isinstance(m, str):
            ms.append(m)
        elif isinstance(m, dict):
            ms.append(f"{m.get('id')}:{m.get('model')}")
    print(f"{args.group}: [{', '.join(ms)}]")


def groups_add(args: argparse.Namespace) -> None:
    devmap = load_config_devices()
    groups = load_config_groups()
    if args.group in groups:
        print(f"Group '{args.group}' already exists.")
        return
    groups[args.group] = []
    save_full_config(devmap, groups)
    print(f"Created group '{args.group}' in {CONFIG_PATH}")


def _parse_pairs(pairs: Optional[List[str]]) -> List[Dict[str, str]]:
    out = []
    if not pairs:
        return out
    for p in pairs:
        if ":" not in p:
            raise GoveeError(f"Invalid pair '{p}'. Expected id:model")
        dev_id, model = p.split(":", 1)
        out.append({"id": dev_id, "model": model})
    return out


def groups_add_members(args: argparse.Namespace) -> None:
    devmap = load_config_devices()
    groups = load_config_groups()
    gname = args.group
    if gname not in groups:
        raise GoveeError(f"Group '{gname}' not found.")
    names = args.names or []
    pairs = _parse_pairs(args.pairs)
    if not names and not pairs:
        raise GoveeError("Provide at least one member via --names or --pairs id:model")
    # Validate nicknames
    for n in names:
        if n not in devmap:
            raise GoveeError(f"Unknown nickname '{n}'. Create it with `names add`.")
    members = groups[gname]
    members.extend(names)
    members.extend(pairs)
    groups[gname] = members
    save_full_config(devmap, groups)
    print(f"Added members to '{gname}'.")


def groups_remove_members(args: argparse.Namespace) -> None:
    devmap = load_config_devices()
    groups = load_config_groups()
    gname = args.group
    if gname not in groups:
        raise GoveeError(f"Group '{gname}' not found.")
    names = set(args.names or [])
    pairs = set(args.pairs or [])
    if not names and not pairs:
        raise GoveeError("Provide members to remove via --names and/or --pairs id:model")
    new_members = []
    for m in groups[gname]:
        if isinstance(m, str):
            if m in names:
                continue
        elif isinstance(m, dict):
            sig = f"{m.get('id')}:{m.get('model')}"
            if sig in pairs:
                continue
        new_members.append(m)
    groups[gname] = new_members
    save_full_config(devmap, groups)
    print(f"Removed members from '{gname}'.")


def groups_remove(args: argparse.Namespace) -> None:
    devmap = load_config_devices()
    groups = load_config_groups()
    if args.group not in groups:
        print(f"Group '{args.group}' not found.")
        return
    del groups[args.group]
    save_full_config(devmap, groups)
    print(f"Removed group '{args.group}'.")


def add_common_target_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--name", help="Nickname from ~/.config/govee_devices.json")
    p.add_argument("--group", help="Group name from ~/.config/govee_devices.json")
    p.add_argument("-d", "--device", help="Govee device ID (from `list`)")
    p.add_argument("-m", "--model", help="Govee model (e.g., H6008)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Control Govee lights via the Cloud API")
    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List devices (shows any configured nicknames)")
    p_list.set_defaults(func=cmd_list)

    # power
    p_power = sub.add_parser("power", help="Turn device on/off")
    p_power.add_argument("state", choices=["on", "off"], help="Desired power state")
    add_common_target_args(p_power)
    p_power.set_defaults(func=cmd_power)

    # brightness
    p_bri = sub.add_parser("brightness", help="Set brightness 0-100")
    p_bri.add_argument("level", type=int, help="Brightness 0-100")
    add_common_target_args(p_bri)
    p_bri.set_defaults(func=cmd_brightness)

    # color
    p_color = sub.add_parser("color", help="Set color")
    g = p_color.add_mutually_exclusive_group(required=True)
    g.add_argument("--hex", help="Hex color like #ff8800")
    g.add_argument("--rgb", nargs=3, metavar=("R", "G", "B"), help="RGB components 0-255")
    add_common_target_args(p_color)
    p_color.set_defaults(func=cmd_color)

    # cct
    p_cct = sub.add_parser("cct", help="Set color temperature in Kelvin")
    p_cct.add_argument("kelvin", type=int, help="Color temperature (e.g., 2700–6500)")
    add_common_target_args(p_cct)
    p_cct.set_defaults(func=cmd_cct)

    # names group
    p_names = sub.add_parser("names", help="Manage device nicknames")
    names_sub = p_names.add_subparsers(dest="names_cmd", required=True)

    p_names_list = names_sub.add_parser("list", help="List nicknames")
    p_names_list.set_defaults(func=names_list)

    p_names_add = names_sub.add_parser("add", help="Add a nickname")
    p_names_add.add_argument("nickname", help="The nickname to create")
    p_names_add.add_argument("-d", "--device", required=True, help="Govee device ID")
    p_names_add.add_argument("-m", "--model", required=True, help="Govee model (e.g., H6008)")
    p_names_add.set_defaults(func=names_add)

    p_names_rm = names_sub.add_parser("remove", help="Remove a nickname")
    p_names_rm.add_argument("nickname", help="The nickname to delete")
    p_names_rm.set_defaults(func=names_remove)

    # groups group
    p_groups = sub.add_parser("groups", help="Manage device groups")
    groups_sub = p_groups.add_subparsers(dest="groups_cmd", required=True)

    p_groups_list = groups_sub.add_parser("list", help="List groups")
    p_groups_list.set_defaults(func=groups_list)

    p_groups_show = groups_sub.add_parser("show", help="Show a group's members")
    p_groups_show.add_argument("group", help="Group name")
    p_groups_show.set_defaults(func=groups_show)

    p_groups_add = groups_sub.add_parser("add", help="Create an empty group")
    p_groups_add.add_argument("group", help="Group name to create")
    p_groups_add.set_defaults(func=groups_add)

    p_groups_rm = groups_sub.add_parser("remove", help="Delete a group")
    p_groups_rm.add_argument("group", help="Group name to delete")
    p_groups_rm.set_defaults(func=groups_remove)

    p_groups_addm = groups_sub.add_parser("add-members", help="Add members to a group")
    p_groups_addm.add_argument("group", help="Group name")
    p_groups_addm.add_argument("--names", nargs="*", help="Nicknames to add")
    p_groups_addm.add_argument("--pairs", nargs="*", help="Inline device pairs id:model to add")
    p_groups_addm.set_defaults(func=groups_add_members)

    p_groups_rmm = groups_sub.add_parser("remove-members", help="Remove members from a group")
    p_groups_rmm.add_argument("group", help="Group name")
    p_groups_rmm.add_argument("--names", nargs="*", help="Nicknames to remove")
    p_groups_rmm.add_argument("--pairs", nargs="*", help="Inline device pairs id:model to remove")
    p_groups_rmm.set_defaults(func=groups_remove_members)

    args = parser.parse_args()
    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(2)
    try:
        args.func(args)
    except GoveeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()