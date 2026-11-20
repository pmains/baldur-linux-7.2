#!/usr/bin/env python3
"""Construct the audited unsigned Android v4 RAM wrapper."""
import hashlib
import json
from pathlib import Path
import struct
import sys

work = Path(sys.argv[1])
out = Path(sys.argv[2])
commit = sys.argv[3]
image = (work / "Image.patched").read_bytes()
dtb = (work / "baldur.dtb").read_bytes()
init = Path("/release/board/init").read_bytes()
cmdline = b"rdinit=/init console=ttynull loglevel=8 printk.time=1 panic=10"
assert image[56:60] == b"ARM\x64" and image.count(dtb) == 1 and image.count(init) == 1
header = struct.pack("<8s9I", b"ANDROID!", len(image), 0, 0, 1584, 0, 0, 0, 0, 4)
header = (header + cmdline).ljust(4096, b"\0")
wrapped = header + image
wrapped += bytes(-len(wrapped) % 4096)
assert len(wrapped) <= 96 * 1024 * 1024
name = "baldur-7.2.15-preview-01.ram.img"
sha = lambda data: hashlib.sha256(data).hexdigest()
(out / name).write_bytes(wrapped)
receipt = {
    "artifact": name,
    "bytes": len(wrapped),
    "sha256": sha(wrapped),
    "source_commit": commit,
    "kernel_release": (work / "include/config/kernel.release").read_text().strip(),
    "kernel_notes_sha256": sha((work / "kernel.notes").read_bytes()),
    "dtb_sha256": sha(dtb),
    "init_sha256": sha(init),
    "local_inputs_manifest_sha256": sha(Path("/release/config/local-inputs.sha256").read_bytes()),
}
(out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(f'{receipt["sha256"]}  {name}')
