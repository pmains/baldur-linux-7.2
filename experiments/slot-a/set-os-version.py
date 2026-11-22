#!/usr/bin/env python3
"""Prepare the exact header-only RAM variant tested in A-selected Fastboot."""
import argparse
import hashlib
from pathlib import Path
import struct

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pilot", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()

image = args.pilot.read_bytes()
expected = "dea30b6c142d889e23496c565210517ba25a98b54d41bfeff6557b3832312285"
if hashlib.sha256(image).hexdigest() != expected:
    parser.error("input hash does not match the qualified slot A pilot wrapper")
if image[:8] != b"ANDROID!" or struct.unpack_from("<I", image, 40) != (4,):
    parser.error("input is not an Android v4 boot wrapper")
if struct.unpack_from("<I", image, 16) != (0,):
    parser.error("expected the original zero os_version field")

corrected = image[:16] + struct.pack("<I", 469762467) + image[20:]
with args.output.open("xb") as output:
    output.write(corrected)
print(hashlib.sha256(corrected).hexdigest(), args.output)
