#!/usr/bin/env python3
"""Create subinterfaces and BGP on a multi-context Cisco ASA from a YAML file."""
import argparse
import getpass
import os
import sys

import yaml
from jinja2 import Environment, FileSystemLoader
from netmiko import ConnectHandler

ERRORS = ("ERROR:", "Invalid input", "% ")


def render(env, name, ctx):
    text = env.get_template(name).render(ctx=ctx)
    return [l for l in text.splitlines() if l.strip()]


def push(conn, cmds, label):
    out = conn.send_config_set(cmds, cmd_verify=False)
    if any(e in out for e in ERRORS):
        raise RuntimeError(f"{label} failed:\n{out}")
    print(f"[ok] {label}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--render-only", action="store_true", help="print commands, do not connect")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(os.path.join(base, "templates")), trim_blocks=True)
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    plan = []
    for ctx in cfg["contexts"]:
        plan.append((ctx["name"], "system", render(env, "system_subif.j2", ctx)))
        plan.append((ctx["name"], "ctx", render(env, "context_if.j2", ctx)
                     + (render(env, "context_bgp.j2", ctx) if ctx.get("bgp") else [])))

    if args.render_only:
        for name, where, cmds in plan:
            print(f"--- {name} ({where}) ---")
            print("\n".join(cmds))
        return

    username = os.environ.get("ASA_USER") or input("ASA username: ")
    password = os.environ.get("ASA_PASS") or getpass.getpass("ASA password: ")
    secret = os.environ.get("ASA_ENABLE") or getpass.getpass("Enable password (blank = same as login): ") or password

    conn = ConnectHandler(
        host=cfg["asa"]["host"],
        device_type=cfg["asa"].get("device_type", "cisco_asa"),
        username=username,
        password=password,
        secret=secret,
    )
    try:
        conn.enable()
        for name, where, cmds in plan:
            try:
                conn.send_command_timing("changeto system" if where == "system"
                                         else f"changeto context {name}")
                push(conn, cmds, f"{name}:{where}")
            except RuntimeError as e:
                print(f"[fail] {e}", file=sys.stderr)
        conn.send_command_timing("changeto system")
        conn.send_command_timing("write memory all")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
