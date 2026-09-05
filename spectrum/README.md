# Spectrum port (Z80)

Nothing here yet. The prototype comes first; this directory exists so the port
is a planned destination rather than a later scramble.

Still to decide (record in the vault, then update this file):

- Assembler (sjasmplus, pasmo, z88dk's z80asm …) and build invocation
- Emulator for the development loop, and how to automate it
- Target model: 48K, or 128K with paging
- Loader and tape/disk image format

`src/` holds assembly source; `build/` holds output and is gitignored.
