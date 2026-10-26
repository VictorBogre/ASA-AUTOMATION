# ASA Multi-Context Provisioning (Subinterfaces + BGP)

Python script that reads a YAML file and configures, on a Cisco ASA running in multi-context mode:

- Subinterfaces and VLANs in the **system** context, allocated to each user context
- Interface settings (nameif, security level, IP) in each **user** context
- BGP (`router bgp`, neighbors, networks) in each user context

Config is applied directly. There is no dry-run gate or backup, so use `--render-only` to preview first.

## Requirements

- Linux with Python 3.8+ and `python3-venv`
- SSH reachability from the Linux host to the ASA, with SSH enabled for your user
- ASA software that supports BGP in multi-context mode (check `show version`)

## Install

```bash
cd asa-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Debian/Ubuntu, if venv creation fails: `sudo apt install python3-venv`.

## Configure

1. Edit `config.yaml`: set `asa.host` and describe each context, its subinterfaces and its BGP settings.
2. Credentials: if `ASA_USER`, `ASA_PASS` and `ASA_ENABLE` are not set, the script prompts for them at run time (password input is hidden). Press Enter at the enable prompt to reuse the login password. Don't put credentials in the YAML. To skip the prompts, export them as environment variables:

```bash
export ASA_USER='admin'
export ASA_PASS='your-password'
export ASA_ENABLE='your-enable-password'   # optional, defaults to ASA_PASS
```

To keep the password out of your shell history, use `read -rs ASA_PASS && export ASA_PASS`.

### YAML example

```yaml
asa:
  host: 10.0.0.1
  device_type: cisco_asa
  bgp_asn: 65100                    # unique system-wide ASN (router bgp)
contexts:
  - name: CTX-A
    subinterfaces:
      - parent: Port-channel1
        id: 100
        mapped_name: ctxa-outside   # optional allocate-interface alias
        nameif: outside
        security_level: 0
        ip: 192.0.2.2
        mask: 255.255.255.0
    bgp:                            # optional
      asn: 65001                    # per-context ASN, used as neighbor local-as
      router_id: 192.0.2.2
      neighbors:
        - ip: 192.0.2.1
          remote_as: 65000
          password: changeme        # optional
      networks:
        - {ip: 10.10.0.0, mask: 255.255.0.0}
```

## BGP ASN model

- `asa.bgp_asn` is the single ASN for the whole ASA. Every context gets `router bgp <bgp_asn>`.
- `bgp.asn` in each context is that context's own ASN. It is applied to every neighbor as `neighbor <ip> local-as <asn> no-prepend replace-as`, so peers see the context ASN instead of the system one.
- To use a different local ASN for one neighbor, add `local_as:` to that neighbor in the YAML.

## Run

Preview the commands without connecting:

```bash
python asa_provision.py --render-only
```

Apply to the ASA:

```bash
python asa_provision.py --config config.yaml
```

For each context the script runs `changeto system` and pushes the subinterface and allocation commands. It then runs `changeto context <name>` and pushes the interface and BGP commands. At the end it returns to the system context and runs `write memory all`. If the ASA returns an error for a context, the script prints it to stderr and moves on to the next one.

## Verify

On the ASA:

```
show context
changeto context CTX-A
show running-config interface
show bgp summary
```

## Notes and caveats

- Subinterfaces can only be created on parent interfaces that already exist in the system context.
- The error check looks for `ERROR:`, `Invalid input` and `% ` in the output. Review the output of your first run.
- Keep `config.yaml` out of version control if it contains BGP passwords.
- Re-running is generally safe because ASA commands can be re-applied, but the script does no diffing and removes nothing.
- A `NETMIKO` timeout or authentication failure usually means SSH is not enabled for your source IP (`ssh <ip> <mask> <interface>`) or the credentials are wrong.
