"""Set PF_X on an ELF64 binary's PT_GNU_STACK program header."""

from pathlib import Path
import struct
import sys


def mark_execstack(path: Path) -> None:
    binary = bytearray(path.read_bytes())
    assert binary[:4] == b"\x7fELF" and binary[4] == 2, "interpreter not ELF64"

    ph_offset = struct.unpack_from("<Q", binary, 0x20)[0]
    ph_entry_size, ph_count = struct.unpack_from("<HH", binary, 0x36)
    pt_gnu_stack, executable = 0x6474E551, 0x1

    for index in range(ph_count):
        offset = ph_offset + index * ph_entry_size
        header_type, flags = struct.unpack_from("<II", binary, offset)
        if header_type == pt_gnu_stack:
            struct.pack_into("<I", binary, offset + 4, flags | executable)
            print(
                f"interpreter: set exec-stack {flags:#x} -> "
                f"{flags | executable:#x}"
            )
            path.write_bytes(binary)
            return

    raise AssertionError("no PT_GNU_STACK program header found in interpreter")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} ELF_BINARY")
    mark_execstack(Path(sys.argv[1]))
