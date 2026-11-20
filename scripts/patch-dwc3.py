#!/usr/bin/env python3
"""Re-apply the first-direct-connect DWC3 workaround to a freshly built Image.

The site offsets and encodings are checked against the actual symbols; the
code cave and BSS flag are re-derived for this build instead of copied.
"""
import hashlib
import struct
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def text_section(obj):
    assert obj[:6] == b'\x7fELF\x02\x01', 'not ELF64 LE'
    section_offset, = struct.unpack_from('<Q', obj, 40)
    size, count, names_index = struct.unpack_from('<HHH', obj, 58)
    sections = [struct.unpack_from('<IIQQQQIIQQ', obj, section_offset + i * size)
                for i in range(count)]
    start, length = sections[names_index][4:6]
    names = obj[start:start + length]
    assert all(s[1] not in (4, 9) for s in sections), 'unresolved relocation'
    text, = [s for s in sections if names[s[0]:].split(b'\0', 1)[0] == b'.text']
    return obj[text[4]:text[4] + text[5]]


def branch(origin, dest, link=False):
    delta = dest - origin
    assert delta % 4 == 0 and -(1 << 27) <= delta < (1 << 27)
    return (0x94000000 if link else 0x14000000) | ((delta // 4) & 0x03ffffff)


def main():
    if len(sys.argv) != 5:
        raise SystemExit("usage: patch-dwc3.py Image vmlinux System.map Image.patched")
    image_path, vmlinux_path, map_path, target_path = map(Path, sys.argv[1:])

    image = image_path.read_bytes()
    symbols = {p[2]: int(p[0], 16) for line in map_path.read_text().splitlines()
               if len(p := line.split()) == 3}
    text = symbols['_text']
    soft = symbols['dwc3_gadget_soft_connect'] - text
    reset = symbols['dwc3_core_soft_reset'] - text
    run_stop = symbols['dwc3_gadget_run_stop'] - text
    pullup = symbols['dwc3_gadget_pullup'] - text
    reset_site, run_site = soft + 0x14, soft + 0x2bc

    # DWC3 codegen must be unchanged from the verified ACM-03 build.
    assert struct.unpack_from('<3I', image, soft) == (0xd100c3ff, 0xa9017bfd, 0x910043fd)
    def bl_target(site, insn):
        assert (insn & 0xfc000000) == 0x94000000, hex(insn)
        imm = insn & 0x03ffffff
        if imm & 0x02000000:
            imm -= 0x04000000
        return site + 4 * imm

    reset_insn, = struct.unpack_from('<I', image, reset_site)
    assert bl_target(reset_site, reset_insn) == reset
    assert struct.unpack_from('<I', image, reset_site + 4)[0] == 0x35001520
    run_insn, = struct.unpack_from('<I', image, run_site - 4)
    assert bl_target(run_site - 4, run_insn) == run_stop
    assert struct.unpack_from('<2I', image, run_site) == (0xa9424ff4, 0xa9417bfd)
    pull_insn, = struct.unpack_from('<I', image, pullup + 0xcc)
    assert bl_target(pullup + 0xcc, pull_insn) == soft
    assert struct.unpack_from('<I', image, pullup + 0xd0)[0] == 0x14000006

    rela = image[symbols['__pi_rela_start'] - text:symbols['__pi_rela_end'] - text]
    relocs = list(struct.iter_unpack('<QQQ', rela))

    # Code cave: zero text padding between __unlikely_text_end and __hot_text_start.
    lo, hi = symbols['__unlikely_text_end'] - text, symbols['__hot_text_start'] - text
    cave = None
    p = (lo + 3) & ~3
    while p + 256 <= hi:
        if image[p:p + 256] == bytes(256):
            cave = p
            break
        p += 4
    assert cave is not None, f'no 256-byte zero cave in text padding {lo:#x}..{hi:#x}'
    assert not any(cave <= a < cave + 256 or (k == 1027 and cave <= v < cave + 256)
                   for a, k, v in relocs), 'relocation covers cave'

    # BSS flag: aligned zero-initialized slot at the end of BSS, no relocations.
    bss_end = symbols['__bss_stop'] - text
    flag = (bss_end - 16) & ~7
    assert symbols['__bss_start'] - text < flag < bss_end - 4
    assert not any(flag <= a < flag + 4 or (k == 1027 and flag <= v < flag + 4)
                   for a, k, v in relocs), 'relocation covers flag'

    obj = target_path.parent / 'dwc3-first-connect.o'
    original = branch(cave + 76, reset)
    resume = branch(cave + 136, run_site + 4)
    subprocess.run(['clang', '-target', 'aarch64-linux-gnu',
                    f'-DCALLER_DELTA={pullup + 0xd0 - cave}',
                    f'-DFLAG_DELTA={flag - cave}',
                    f'-DRUN_RETURN_DELTA={run_site - cave}',
                    f'-DORIGINAL_RESET={original}',
                    f'-DRUN_RESUME={resume}',
                    '-c', str(OUT / 'dwc3-first-connect.S'), '-o', str(obj)], check=True)
    code = text_section(obj.read_bytes())
    assert len(code) < 256, len(code)
    assert struct.unpack_from('<2I', code, 72) == (0xd5033f5f, original)
    assert struct.unpack_from('<2I', code, 132) == (0xa9424ff4, resume)

    # No pre-existing direct branch may target the cave.
    listing = subprocess.check_output(['llvm-objdump', '-d', str(vmlinux_path)], text=True)
    import re
    for line in listing.splitlines():
        m = re.search(r'\b(?:b(?:l|\.\w+)?|cbn?z|tbn?z)\s+[^<]*?\b(?:0x)?([0-9a-f]{8,16}) <', line)
        if m:
            assert not (text + cave <= int(m.group(1), 16) < text + cave + 256), line

    result = bytearray(image)
    result[cave:cave + len(code)] = code
    struct.pack_into('<I', result, reset_site, branch(reset_site, cave, True))
    struct.pack_into('<I', result, run_site, branch(run_site, cave + 96))
    target_path.write_bytes(result)

    report = {
        'input_sha256': sha(bytes(image)),
        'output_sha256': sha(bytes(result)),
        'bytes': len(result),
        'text_offset': hex(text),
        'soft_connect': hex(soft),
        'reset_site': hex(reset_site),
        'run_site': hex(run_site),
        'pullup': hex(pullup),
        'cave': hex(cave),
        'flag': hex(flag),
        'code_bytes': len(code),
    }
    (target_path.parent / 'patch-report.json').write_text(__import__('json').dumps(report, indent=2) + '\n')
    print(f'patched {len(result)} bytes; cave Image+{cave:#x}; flag Image+{flag:#x}')
    print(f'SHA-256 {sha(bytes(result))}')


if __name__ == '__main__':
    main()
