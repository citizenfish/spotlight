; Spotlight, the 48K port: the first slice (issue #153).
;
; A 50Hz loop that draws one room. The thinnest thing that runs end to end --
; a cleared play area, one authored room's walls and floor from a bit-packed
; shell, the player on it, the keyboard read -- so that the loop, the screen
; model, the asset format and the test harness are all proved at once.
;
; `DEVICE ZXSPECTRUM48` pins the model: a build that outgrows 48K fails here
; rather than quietly paging. See *The port begins* in the vault.
;
; Held to two tests in `prototype/tests/test_port_room.py`: the screen bytes
; against the prototype's `core.screen.Screen` for the same room, and one
; frame's T-states against `ENTITY_CEILING`.

        DEVICE ZXSPECTRUM48

PLAY_ROWS       EQU 22          ; the play area; the strip is the last two
COLS            EQU 32
SCREEN          EQU $4000
ATTRS           EQU $5800
THIRD           EQU $0800       ; bytes in one third of the display file

; Bright white on black, the whole play area. The light field is the next
; slice; until it exists a room is drawn lit so there is something to compare.
PLAY_ATTR       EQU %01000111

; Where the player stands, in cells. Cell-aligned on purpose: shifting a
; sprite to an arbitrary pixel column is the sprite routine's own slice, and
; this one is about the loop.
PLAYER_CX       EQU 5
PLAYER_CY       EQU 12

        ORG $8000

; --- the loop ---------------------------------------------------------------

main:
        xor     a
        out     ($fe), a                ; black border
        call    enter_room
        call    draw_player
.loop:  halt                            ; the 50Hz interrupt, and nothing else
        call    draw_frame
        jr      .loop

; **Entering a room, not a frame's work.** Measured, the whole-room draw is
; 755,953 T-states and the clear another 133,722 -- together about **thirteen
; frames**, against an `ENTITY_CEILING` of 32,832 and a 50Hz frame of 70,000.
;
; A Z80 cannot repaint 704 cells at 50Hz and this game never asks it to: a room
; is revealed by the beam, a few cells at a time, and a room nobody is looking
; at keeps its charge and not its picture (issue #136, measured there as 3.00
; display rebuilds a frame falling to 1.00). So the whole-room draw is what it
; costs to arrive somewhere, and the per-frame budget is spent on the cells that
; actually changed.
enter_room:
        call    build_masks
        call    clear_play
        call    draw_room
        ret

; One frame's drawing, and only that: put the room back where the player was
; standing, then draw them where they are. The tests call this and count what
; it costs, so nothing that is not per-frame work belongs in it.
draw_frame:
        call    erase_player
        call    read_keys
        call    draw_player
        ret

; Everything the screen needs on arrival, for the test that compares the
; picture against the prototype's.
draw_all:
        call    enter_room
        call    draw_player
        ret

; The two cells the player occupies, redrawn as room. A sprite is erased by
; putting back what it stood on -- there is no saved background and no need of
; one, because a cell's contents are a function of the room and its position.
erase_player:
        ld      a, (player_cx)
        ld      c, a
        ld      a, (player_cy)
        ld      b, a
        push    bc
        call    draw_cell
        pop     bc
        inc     b
        call    draw_cell
        ret

; --- the play area, cleared -------------------------------------------------
;
; Thirds 0 and 1 are the first sixteen character rows and are contiguous, so
; they go with one `ldir` each. The third third holds rows 16-23 and only
; 16-21 are ours: within a third a character row sits at `(cy & 7) * 32`, so
; rows 16-21 are offsets 0-191 at each of the eight pixel rows -- eight runs
; of 192 bytes rather than one.

clear_play:
        ld      hl, SCREEN
        ld      de, SCREEN + 1
        ld      bc, THIRD * 2 - 1
        ld      (hl), 0
        ldir                            ; rows 0-15

        ld      hl, SCREEN + THIRD * 2
        ld      c, 8                    ; the eight pixel rows of the third
.band:  push    hl
        ld      d, h
        ld      e, l
        inc     de
        ld      (hl), 0
        ld      b, 0
        push    bc
        ld      bc, 192 - 1             ; rows 16-21 at this pixel row
        ldir
        pop     bc
        pop     hl
        inc     h                       ; next pixel row of the same third
        dec     c
        jr      nz, .band

        ld      hl, ATTRS
        ld      de, ATTRS + 1
        ld      bc, COLS * PLAY_ROWS - 1
        ld      (hl), PLAY_ATTR
        ldir
        ret

; --- the room ---------------------------------------------------------------
;
; For every cell: solid cells wear one of the sixteen wall tiles, chosen by
; their four neighbours; floor wears one of sixteen blocks chosen by position,
; `(cy & 3) * 4 + (cx & 3)`, which is `floor.py`'s rule and the reason the
; stipple does not tile visibly.

draw_room:
        ld      b, 0                    ; cy
.row:   ld      c, 0                    ; cx
.cell:  push    bc
        call    draw_cell
        pop     bc
        inc     c
        ld      a, c
        cp      COLS
        jr      nz, .cell
        inc     b
        ld      a, b
        cp      PLAY_ROWS
        jr      nz, .row
        ret

; One cell of room: the tile its own geometry and position choose.
;
; in: B = cy, C = cx
draw_cell:
        push    bc
        call    tile_of                 ; DE = the tile's eight bytes
        pop     bc
        call    cell_addr               ; HL = the cell, top pixel row
        call    blit_tile
        ret

; Which tile a cell wears: **three reads and no arithmetic** (issue #154).
;
; It began as four `is_solid` calls at 292 T-states each -- 1,331 for the mask,
; 64% of a wall cell, and nearly ten times what `tiles.mask_at` costed the whole
; mask at. Caching the mask took it to 228. Caching the **pre-doubled index into
; one tile table** takes it to about a hundred, because the cell's whole
; identity is then one byte:
;
;   * a wall cell's index is its four-neighbour mask, 0 to 15;
;   * a floor cell's is 16 + `(cy & 3) * 4 + (cx & 3)`, which is a function of
;     the cell's **position** and so is just as constant as the mask;
;   * both are stored doubled, because the table holds words.
;
; **None of it is lighting.** The index says which of the sixteen wall shapes or
; sixteen floor blocks a cell is; which *table* -- lit or remembered -- the
; light field chooses, and that is the next slice's to vary. Caching a tile
; pointer instead would have baked the light level into the cache and had to be
; rebuilt every frame, which is the thing being avoided.
;
; in:  B = cy, C = cx
; out: DE = eight bytes of tile. **BC survives; HL and A do not.**
tile_of:
        ld      a, b                    ; the cached index for this cell
        add     a, a
        add     a, IDX_ROW & $FF
        ld      l, a
        ld      h, IDX_ROW >> 8
        ld      a, (hl)
        inc     l                       ; the table is page-aligned
        ld      h, (hl)
        add     a, c
        ld      l, a
        ld      a, (hl)                 ; A = the index, doubled
        ld      l, a
        ld      h, TILES >> 8           ; ...and the table is page-aligned too,
        ld      e, (hl)                 ; so the index *is* the low byte
        inc     l
        ld      d, (hl)
        ret

; Every cell's tile index, worked out once on arrival (`enter_room`). 704 bytes
; of working store: *The port begins* measured that memory is not this machine's
; constraint -- the art is 1,704 bytes with 42,240 free -- while cycles are.
build_masks:
        ld      b, 0
.row:   ld      c, 0
.cell:  push    bc
        call    is_solid
        jr      z, .floor
        call    mask_at                 ; 0-15, the four-neighbour mask
        jr      .store
.floor: ld      a, b
        and     %00000011               ; cy & 3
        add     a, a
        add     a, a                    ; * 4
        ld      e, a
        ld      a, c
        and     %00000011               ; cx & 3
        add     a, e
        add     a, 16                   ; the floor blocks follow the walls
.store: add     a, a                    ; doubled: the table holds words
        pop     bc
        push    bc
        push    af
        call    idx_addr
        pop     af
        ld      (hl), a
        pop     bc
        inc     c
        ld      a, c
        cp      COLS
        jr      nz, .cell
        inc     b
        ld      a, b
        cp      PLAY_ROWS
        jr      nz, .row
        ret

; Where a cell's cached index lives. Only `build_masks` calls this -- `tile_of`
; has it inlined, because at 62 T-states the `call` and `ret` are a fifth of it.
;
; in:  B = cy, C = cx ; out: HL = the byte's address. BC survives.
idx_addr:
        ld      a, b
        add     a, a
        add     a, IDX_ROW & $FF
        ld      l, a
        ld      h, IDX_ROW >> 8
        ld      a, (hl)
        inc     l
        ld      h, (hl)
        add     a, c
        ld      l, a
        ret

; Eight bytes into one cell. Within a character cell the next pixel row is
; the next value of the address's high byte, so stepping down is `inc h`.
;
; in:  HL = the cell's top row, DE = tile data
; Unrolled (issue #154): the loop was `ld a,(de) : ld (hl),a : inc de : inc h :
; djnz` at 37 T-states a row; straight through it is 24, so the eight rows cost
; about 192 against 296. Twelve bytes of code for a hundred T-states a cell, and
; a cell is the port's currency.
blit_tile:
        ld      a, (de) : ld (hl), a : inc de : inc h
        ld      a, (de) : ld (hl), a : inc de : inc h
        ld      a, (de) : ld (hl), a : inc de : inc h
        ld      a, (de) : ld (hl), a : inc de : inc h
        ld      a, (de) : ld (hl), a : inc de : inc h
        ld      a, (de) : ld (hl), a : inc de : inc h
        ld      a, (de) : ld (hl), a : inc de : inc h
        ld      a, (de) : ld (hl), a
        ret

; --- the room's geometry ----------------------------------------------------
;
; One bit a cell, 22 rows of 4 bytes, bit 7 the leftmost cell (`tools/rooms.py`).
; **Off the room counts as solid** and is not stored: an unsigned compare does
; it for nothing, because -1 arrives as 255 and fails `cp` against the bound
; the same way 32 does. That is what makes the outer wall show one face.
;
; in:  B = cy, C = cx
; out: Z if the cell is clear, NZ if it is solid. BC survives.
is_solid:
        push    bc
        push    hl
        push    de
        ld      a, b
        cp      PLAY_ROWS
        jr      nc, .solid
        ld      a, c
        cp      COLS
        jr      nc, .solid

        ld      hl, DOGLEG
        ld      a, b
        add     a, a
        add     a, a                    ; cy * 4, the row's stride
        add     a, l
        ld      l, a
        jr      nc, .nc1
        inc     h
.nc1:   ld      a, c
        rrca
        rrca
        rrca
        and     %00000011               ; cx >> 3
        add     a, l
        ld      l, a
        jr      nc, .nc2
        inc     h
.nc2:   ld      a, c
        and     %00000111
        ld      de, BIT_OF
        add     a, e
        ld      e, a
        jr      nc, .nc3
        inc     d
.nc3:   ld      a, (de)
        and     (hl)                    ; Z if the bit is clear
        jr      .out

.solid: ld      a, 1
        and     a                       ; NZ
.out:   pop     de
        pop     hl
        pop     bc
        ret

; The four-neighbour mask, north east south west as 1 2 4 8 -- `tiles.py`'s own
; order, so the sixteen wall tiles are indexed identically on both machines.
;
; in:  B = cy, C = cx
; out: A = the mask. BC survives.
mask_at:
        push    bc
        xor     a
        ld      (mask_acc), a

        dec     b                       ; north
        call    is_solid
        jr      z, .east
        ld      a, (mask_acc)
        or      1
        ld      (mask_acc), a
.east:  pop     bc
        push    bc
        inc     c                       ; east
        call    is_solid
        jr      z, .south
        ld      a, (mask_acc)
        or      2
        ld      (mask_acc), a
.south: pop     bc
        push    bc
        inc     b                       ; south
        call    is_solid
        jr      z, .west
        ld      a, (mask_acc)
        or      4
        ld      (mask_acc), a
.west:  pop     bc
        push    bc
        dec     c                       ; west
        call    is_solid
        jr      z, .done
        ld      a, (mask_acc)
        or      8
        ld      (mask_acc), a
.done:  pop     bc
        ld      a, (mask_acc)
        ret

; --- addresses --------------------------------------------------------------
;
; The display file's own shape: for character row cy and pixel row dy,
;   H = $40 | (cy & $18) | dy      L = ((cy & 7) << 5) | cx
; so the three parts never interfere and stepping a pixel row is `inc h`.
;
; in:  B = cy, C = cx ; out: HL = that cell's top pixel row
; A table read (issue #154), where it was two masks, three rotations and an
; `or`. Twenty-two words, one a character row.
;
; **It must not touch DE**, because `draw_cell` is holding the tile pointer
; there -- the first cut of this did `ld de, ROW_ADDR` and drew the whole room
; out of whatever the row table happened to point at. `ROW_ADDR` is page-aligned
; instead, so the index is one byte: `cy * 2` plus the table's offset inside its
; page, which cannot carry because 21*2 + 192 is still under 256.
cell_addr:
        ld      a, b
        add     a, a                    ; two bytes an entry
        add     a, ROW_ADDR & $FF
        ld      l, a
        ld      h, ROW_ADDR >> 8
        ld      a, (hl)                 ; the row's low byte
        inc     l                       ; cannot leave the page, as above
        ld      h, (hl)                 ; ...and its high byte
        add     a, c                    ; + cx, which cannot carry: the low byte
        ld      l, a                    ; is a multiple of 32 and cx < 32
        ret

; in:  B = cy, C = cx ; out: HL = that cell's attribute
attr_addr:
        ld      h, 0
        ld      l, b
        add     hl, hl
        add     hl, hl
        add     hl, hl
        add     hl, hl
        add     hl, hl                  ; cy * 32
        ld      e, c
        ld      d, 0
        add     hl, de
        ld      de, ATTRS
        add     hl, de
        ret

; --- the player -------------------------------------------------------------
;
; Sixteen rows over two cells. The mask's set bits are the pixels to clear, so
; the Z80 does `cpl : and (hl) : or ink` -- which is the same picture as the
; prototype's clear-then-set, and `sprites.draw` says so in as many words.

draw_player:
        ld      de, PLAYER_N
        ld      ix, PLAYER_N_MASK
        ld      a, (player_cy)
        ld      b, a
        ld      a, (player_cx)
        ld      c, a
        call    cell_addr
        ld      b, 8
        call    sprite_rows
        ld      a, (player_cy)
        inc     a
        ld      b, a
        ld      a, (player_cx)
        ld      c, a
        call    cell_addr
        ld      b, 8
        call    sprite_rows
        ret

; in: HL = screen, DE = ink, IX = mask, B = rows
sprite_rows:
.row:   ld      a, (de)
        ld      c, a                    ; the ink for this row
        ld      a, (ix+0)
        cpl                             ; mask: 1 clears, so AND the complement
        and     (hl)
        or      c
        ld      (hl), a
        inc     de
        inc     ix
        inc     h
        djnz    .row
        ret

; --- the keyboard -----------------------------------------------------------
;
; Q A O P, one cell a press. No repeat delay and no collision: this slice is
; about the loop, and the player walks pixel by pixel into a solidity test in
; the slice that owns movement.

read_keys:
        ld      a, (player_cy)
        ld      d, a
        ld      a, (player_cx)
        ld      e, a

        ld      bc, $fbfe               ; Q W E R T
        in      a, (c)
        bit     0, a
        jr      nz, .not_q
        dec     d
.not_q: ld      bc, $fdfe               ; A S D F G
        in      a, (c)
        bit     0, a
        jr      nz, .not_a
        inc     d
.not_a: ld      bc, $dffe               ; P O I U Y
        in      a, (c)
        bit     1, a
        jr      nz, .not_o
        dec     e
.not_o: bit     0, a
        jr      nz, .done
        inc     e

.done:  ld      a, d                    ; keep the pair on the play area
        cp      PLAY_ROWS - 1
        jr      nc, .no_y
        ld      a, d
        ld      (player_cy), a
.no_y:  ld      a, e
        cp      COLS
        jr      nc, .no_x
        ld      a, e
        ld      (player_cx), a
.no_x:  ret

; --- tables -----------------------------------------------------------------

BIT_OF:
        DEFB $80,$40,$20,$10,$08,$04,$02,$01

; Each character row's screen address, which the display file's own shape makes
; non-linear: H = $40 | (cy & $18) | dy, L = (cy & 7) << 5.
;
; **Page-aligned** so `cell_addr` can index it with one byte and leave DE alone.
        ALIGN 64
ROW_ADDR:
cy = 0
        DUP PLAY_ROWS
        DEFW $4000 | ((cy & $18) << 8) | ((cy & 7) << 5)
cy = cy + 1
        EDUP

; And each row of the index cache, for the same reason: one byte of index
; arithmetic instead of five `add hl,hl`.
        ALIGN 64
IDX_ROW:
cy = 0
        DUP PLAY_ROWS
        DEFW IDX + cy * COLS
cy = cy + 1
        EDUP

; **One table, page-aligned**: sixteen wall shapes then sixteen floor blocks, so
; a cell's cached index is literally the low byte of its entry's address and
; `tile_of` needs no arithmetic at all. Sixty-four bytes, and the alignment is
; what buys the three-read lookup.
;
; The light field will want a second one of these for remembered cells
; (`WALL_DIM`, `FLOOR_DIM`); it is a different table, not a different index,
; which is why the cache holds the index and not a pointer.
        ALIGN 256
TILES:
        DEFW WALL_LIT_00, WALL_LIT_01, WALL_LIT_02, WALL_LIT_03
        DEFW WALL_LIT_04, WALL_LIT_05, WALL_LIT_06, WALL_LIT_07
        DEFW WALL_LIT_08, WALL_LIT_09, WALL_LIT_10, WALL_LIT_11
        DEFW WALL_LIT_12, WALL_LIT_13, WALL_LIT_14, WALL_LIT_15
        DEFW FLOOR_LIT_00, FLOOR_LIT_01, FLOOR_LIT_02, FLOOR_LIT_03
        DEFW FLOOR_LIT_04, FLOOR_LIT_05, FLOOR_LIT_06, FLOOR_LIT_07
        DEFW FLOOR_LIT_08, FLOOR_LIT_09, FLOOR_LIT_10, FLOOR_LIT_11
        DEFW FLOOR_LIT_12, FLOOR_LIT_13, FLOOR_LIT_14, FLOOR_LIT_15

; --- state ------------------------------------------------------------------

mask_acc:   DEFB 0
player_cx:  DEFB PLAYER_CX
player_cy:  DEFB PLAYER_CY

; --- the generated tables ---------------------------------------------------

        INCLUDE "rooms.asm"
        INCLUDE "bitmaps.asm"

code_end:
        SAVEBIN "../build/spotlight.bin", main, code_end - main

; --- the mask cache ---------------------------------------------------------
;
; 704 bytes of working store, **after** the saved image so it costs nothing on
; tape: it is built on arrival, never loaded. One byte a cell: a wall's
; four-neighbour mask, or $FF for floor.

; **Page-aligned**, so a row's low byte is a multiple of 32 and adding `cx`
; cannot carry -- which is what lets `tile_of` do `add a,c : ld l,a` with no
; carry branch.
IDX:    EQU (code_end + 255) & $FF00
IDX_END: EQU IDX + COLS * PLAY_ROWS
