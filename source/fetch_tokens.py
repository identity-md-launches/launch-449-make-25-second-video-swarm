#!/usr/bin/env python3
"""Save SVGs returned by PixelArt.renderSVG(SwarmPepe.seedOf(id))."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


RPC = os.environ.get("ETH_RPC", "https://ethereum-rpc.publicnode.com")
SWARM = "0x999ce0ce8c5f7661e0c74a568ffe27ceb9177bdb"
ART = "0x07Fd9841eEB6a359EfB30f861D59bFa1f6B03FcA"
SEED_OF = "82829f74"
OWNER_OF = "6352211e"
RENDER_SVG = "d12a4c98"
ROOT = Path(__file__).resolve().parent.parent


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    response = subprocess.run(["curl", "-fsS", "--max-time", "45", "-H",
                               "Content-Type: application/json", "--data-binary",
                               "@-", RPC], input=body, capture_output=True, check=True)
    result = json.loads(response.stdout)
    if "error" in result:
        raise RuntimeError(f"{method}: {result['error']}")
    return result["result"]


def call(to, selector, arg, block):
    data = "0x" + selector + f"{arg:064x}"
    return bytes.fromhex(rpc("eth_call", [{"to": to, "data": data}, block])[2:])


def decode_string(data):
    offset = int.from_bytes(data[:32], "big")
    length = int.from_bytes(data[offset:offset + 32], "big")
    return data[offset + 32:offset + 32 + length].decode()


def main(ids):
    block = rpc("eth_blockNumber", [])
    records = []
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    for token_id in ids:
        # ownerOf reverts for nonexistent tokens; a nonzero seed checks reveal.
        call(SWARM, OWNER_OF, token_id, block)
        seed = int.from_bytes(call(SWARM, SEED_OF, token_id, block), "big")
        if seed == 0:
            print(f"#{token_id}: unrevealed; skipped", file=sys.stderr)
            continue
        svg = decode_string(call(ART, RENDER_SVG, seed, block))
        if not svg.startswith("<svg") or "viewBox=\"0 0 24 24\"" not in svg:
            raise RuntimeError(f"Unexpected SVG for #{token_id}")
        name = f"token_{token_id:04d}.svg"
        (out / name).write_text(svg)
        records.append({"token_id": token_id, "seed": str(seed), "svg": name,
                        "sha256": hashlib.sha256(svg.encode()).hexdigest()})
        print(f"#{token_id}: saved {name} ({len(svg)} bytes)")
    (out / "provenance.json").write_text(json.dumps({
        "chain": "Ethereum mainnet", "block": block,
        "swarm_pepe_contract": SWARM, "pixel_art_contract": ART,
        "calls": ["SwarmPepe.ownerOf(id)", "SwarmPepe.seedOf(id)",
                  "PixelArt.renderSVG(seed)"], "tokens": records
    }, indent=2) + "\n")


if __name__ == "__main__":
    main([int(arg) for arg in sys.argv[1:]])
