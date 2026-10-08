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

; The light field's own constants, which are `spikes/lighting.py`'s and must
; stay its (issue #155). The one tuning knob is the fade.
FADE_FRAMES     EQU 150         ; three seconds, lit to black
LIT_FRAMES      EQU 30          ; a fifth of it: how long a cell still reads lit
LIT_THRESHOLD   EQU 120         ; above this LIT, above nought DIM, else DARK
CHARGE_LIT      EQU 150         ; a full top-up
CHARGE_SWEEP    EQU 10          ; the beam's wake on the floor
CHARGE_WALL     EQU 150         ; and on a wall, which is how a room is known

DARK            EQU 0
DIM             EQU 1
LIT             EQU 2

; The room's hue. **Light decides brightness; the cell's contents decide hue**
; -- so this is the contents' half, one ink for the floor and walls of a room,
; and the level supplies the BRIGHT bit on top.
ROOM_INK        EQU 6           ; yellow, which is what `hue_at` gives this room

; The beam: a disc of 37 cells, seven rows of half-widths. **The same table the
; magnet fires by** in the prototype, so the drawn edge is the rule's edge.
BEAM_RADIUS     EQU 3

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
        call    light_frame
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
        call    clear_schedule          ; nothing is filed and nothing is due
        call    clear_shown             ; nothing is drawn yet, so: all dark
        call    clear_play
        call    draw_room
        ret

; Arriving draws every cell at the level it is showing, and `draw_room` has
; just done that -- but `SHOWN` has to agree, or the first frame would repaint
; the whole room again. The field is empty on arrival, so every cell is dark.
clear_shown:
        ld      hl, SHOWN
        ld      de, SHOWN + 1
        ld      bc, COLS * PLAY_ROWS - 1
        ld      (hl), DARK
        ldir
        ret

; One frame's drawing, and only that: put the room back where the player was
; standing, then draw them where they are. The tests call this and count what
; it costs, so nothing that is not per-frame work belongs in it.
draw_frame:
        call    paint_changed
        call    erase_player
        call    read_keys
        call    draw_player
        ret

; Every cell whose level has moved since it was last drawn, redrawn at the
; level it is showing now.
;
; `SHOWN` holds the level each cell was last drawn at, so this is the exact
; repaint set and not an approximation -- which byte-identity with the prototype
; demands, because the fade crosses a threshold on frames nothing wrote to the
; cell and those cells still have to change on screen.
;
; **It is told which cells, not asked** (issue #156). Asking all 704 cost
; 277,322 T-states a frame -- 845% of `ENTITY_CEILING` -- to find the eight that
; moved on a median frame. A cell's charge is deterministic, so the frame it next
; changes level is known the moment it is written, and `schedule` files it under
; that frame. Here the bucket for this frame is walked and nothing else.
;
; Two sources of change, and both are handled:
;
;   * **the fade** crossing a threshold, which is what the schedule holds;
;   * **the beam moving**, which makes cells it has left stop reading `LIT`
;     whatever their charge says. Those are the disc's own cells, and only when
;     the beam actually moves -- at `pace: 6` that is one frame in six.
paint_changed:
        call    due_now                 ; the fade's own transitions
        call    beam_edges              ; and the cells the beam left behind
        ret

; The cells filed under this frame, each checked and redrawn if it has moved,
; then re-filed for whenever it next changes.
due_now:
        ld      a, (DECAYS)
        call    head_addr               ; HL = the bucket for this frame
        ld      e, (hl)
        inc     h
        ld      d, (hl)                 ; DE = the first cell in it, or nil
        dec     h
        ld      (hl), $FF               ; the bucket is emptied as it is walked
        inc     h
        ld      (hl), $FF

.next:  ld      a, d
        and     e
        inc     a
        ret     z                       ; nil: the chain is done

        push    de
        ; The link to the next cell before this one is touched, because
        ; re-filing it will overwrite its link.
        ld      hl, LINK_LO
        add     hl, de
        ld      c, (hl)
        ld      hl, LINK_HI
        add     hl, de
        ld      b, (hl)
        push    bc                      ; the rest of the chain

        ; **Is this entry still the live one?** `DUE` is the authority, and
        ; there are three answers, not two:
        ;
        ;   * its low byte disagrees with this frame -- the cell was re-written
        ;     and filed somewhere else, so this entry is **stale** and dropped,
        ;     which is what keeps the chains from multiplying;
        ;   * it agrees entirely -- the cell is **due**, so check and re-file;
        ;   * it agrees in the low byte but not the high -- the cell is due in
        ;     some multiple of 256 frames' time and this bucket has merely come
        ;     round early, so **put it back**.
        ;
        ; That last case is not hypothetical and was the bug: a wall holds
        ; `CHARGE_WALL` at half rate, so it is due **299 frames** out, past the
        ; horizon of 256 buckets. Dropping those entries meant a swept wall was
        ; never looked at again and stayed lit for ever.
        ; **Out of the chain now**, because walking a bucket empties it. So this
        ; is the one moment a cell can be moved without corrupting anything.
        ld      hl, FILED
        add     hl, de
        ld      (hl), $FF

        ld      hl, DUE_LO
        add     hl, de
        ld      a, (hl)
        ld      hl, (DECAYS)
        cp      l
        jr      nz, .elsewhere          ; due on some other frame: re-file
        ld      hl, DUE_HI
        add     hl, de
        ld      a, (hl)
        ld      hl, (DECAYS)
        cp      h
        jr      z, .due

.elsewhere:
        ; Not due now -- either the cell was written since and its due frame
        ; moved, or it is due in a multiple of 256 frames' time and this bucket
        ; has merely come round early. A wall holds `CHARGE_WALL` at half rate
        ; and is due **299 frames** out, past the horizon of 256 buckets, so
        ; this case is ordinary rather than exotic.
        ld      hl, DUE_LO
        add     hl, de
        ld      a, (hl)
        inc     a
        jr      z, .stale               ; no due frame at all: nothing to file
        dec     a
        call    file_cell
        jr      .stale

.due:   ld      b, d                    ; the index, high byte in B as
        ld      c, e                    ; `cell_of` wants it
        call    cell_of                 ; B = cy, C = cx
        push    bc
        call    check_cell
        pop     bc
        call    reschedule
.stale: pop     bc                      ; the rest of the chain
        pop     de
        ld      e, c
        ld      d, b
        jr      .next

; One cell: redraw it if what it shows has moved from what was drawn.
;
; in:  B = cy, C = cx
check_cell:
        push    bc
        call    level_at
        ld      e, a
        push    de
        call    shown_addr
        pop     de
        ld      a, (hl)
        cp      e
        jr      z, .same
        ld      (hl), e                 ; remember what we are about to draw
        pop     bc
        jp      draw_cell
.same:  pop     bc
        ret

; The cells the beam has stopped covering, and the ones it has started. Only
; when it has moved: at `pace: 6` the beam holds its cell for six frames, and on
; those frames nothing enters or leaves the disc at all.
beam_edges:
        ld      a, (BEAM_X)
        ld      hl, (WAS_BEAM)
        cp      l
        jr      nz, .moved
        ld      a, (BEAM_Y)
        cp      h
        ret     z                       ; it has not moved: nothing to do

.moved: ; **The cells the beam has left.** They were lit by it and may not be any
        ; more, so each is checked -- and this is where they are scheduled, the
        ; work `write_charge` deliberately does not do while the beam is on
        ; them. The cells the beam has just *reached* are written and drawn by
        ; `beam_emit`, so they need nothing here.
        ld      hl, (WAS_BEAM)
        ld      a, l
        ld      (disc_x), a
        ld      a, h
        ld      (disc_y), a
        call    check_disc
        ld      a, (BEAM_X)
        ld      l, a
        ld      a, (BEAM_Y)
        ld      h, a
        ld      (WAS_BEAM), hl
        ret

; Is a cell inside the beam's disc as it stands now? Z if it is.
;
; in:  B = cy, C = cx ; out: Z if inside. BC survives.
in_beam:
        ld      a, (BEAM_Y)
        sub     b
        jr      nc, .dy
        neg
.dy:    cp      BEAM_RADIUS + 1
        jr      nc, .out                ; too far up or down
        ; **The row's half-width is `DISC[radius - |dy|]`**, not `DISC[|dy|]`:
        ; the table runs from the disc's top row to its bottom, so the centre
        ; is in the middle of it. Indexing by the distance from the centre read
        ; the widths inside out -- a one-cell band where the disc is widest.
        ld      e, a
        ld      a, BEAM_RADIUS
        sub     e
        ld      hl, DISC
        add     a, l
        ld      l, a
        jr      nc, .nc
        inc     h
.nc:    ld      a, (hl)
        ld      e, a
        ld      a, (BEAM_X)
        sub     c
        jr      nc, .dx
        neg
.dx:    cp      e
        jr      z, .in
        jr      c, .in
.out:   ld      a, 1
        and     a                       ; NZ: outside
        ret
.in:    xor     a                       ; Z: inside
        ret

; Every cell of the disc centred on `disc_x`, `disc_y`, checked.
check_disc:
        ld      a, (disc_y)
        sub     BEAM_RADIUS
        ld      b, a
        ld      ix, DISC
        ld      a, BEAM_RADIUS * 2 + 1
        ld      (disc_rows), a
.row:   ld      a, (disc_x)
        sub     (ix+0)
        ld      c, a
        ld      a, (ix+0)
        add     a, a
        inc     a
        ld      (disc_cells), a
.cell:  ld      a, b
        cp      PLAY_ROWS
        jr      nc, .skip               ; off the room: nothing to draw
        ld      a, c
        cp      COLS
        jr      nc, .skip
        ; **Only the cells it actually left.** A cell still inside the new disc
        ; is still lit, so it has not changed and needs no schedule -- the same
        ; argument as the write path's. When the beam steps one cell, seven of
        ; the thirty-seven leave; checking and rescheduling all of them cost
        ; 139,862 T-states a frame, four times the budget, to do seven cells'
        ; worth of work.
        push    bc
        call    in_beam
        pop     bc
        jr      z, .skip
        push    bc
        call    check_cell
        pop     bc
        push    bc
        call    reschedule              ; now that the beam has gone
        pop     bc
.skip:  inc     c
        ld      a, (disc_cells)
        dec     a
        ld      (disc_cells), a
        jr      nz, .cell
        inc     b
        inc     ix
        ld      a, (disc_rows)
        dec     a
        ld      (disc_rows), a
        jr      nz, .row
        ret

; --- the schedule ----------------------------------------------------------
;
; One bucket a frame, 256 of them, and one live entry a cell. Filing is three
; stores; firing is the chain for this frame and nothing else.

; File a cell under the frame it next changes level at.
;
; in:  B = cy, C = cx, HL = &CHARGE[cell] is **not** needed -- the charge is
;      read here -- and DE is spent.
; **A cell is filed at most once, and that is the whole correctness argument.**
;
; The first cut filed it again on every write, and a cell re-filed while still
; linked into an older chain had its link overwritten -- which orphaned every
; entry behind it in that chain. Cells simply vanished from the schedule and
; stayed lit for ever; the one I chased was (2,2), due at frame 22 and present
; in no bucket at all.
;
; So `FILED` records which bucket a cell is in, and a write only *files* a cell
; that is not filed already. A write to a cell that is already filed just moves
; `DUE`; the entry sitting in the old bucket will come up, find itself not due,
; and re-file under the new `DUE` -- which is safe, because walking a bucket
; empties it, so an entry being processed is in no chain at all.
reschedule:
        push    bc
        call    next_change             ; HL = the frame it next changes at
file_at:
        ld      (sched_at), hl
        call    cell_index              ; DE = the cell's index
        ld      hl, DUE_LO
        add     hl, de
        ld      a, (sched_at)
        ld      (hl), a
        ld      hl, DUE_HI
        add     hl, de
        ld      a, (sched_at + 1)
        ld      (hl), a

        ld      a, (sched_at)
        and     a
        ld      a, (sched_at + 1)
        inc     a
        jr      z, .done                ; `$FFFF`: it will not change again

        ld      hl, FILED
        add     hl, de
        ld      a, (hl)
        inc     a
        jr      nz, .done               ; already in a bucket: leave it there
        ld      a, (sched_at)
        call    file_cell
.done:  pop     bc
        ret

; Put a cell at the head of a bucket's chain. Three stores and no search, which
; is the whole point of the schedule.
;
; in:  DE = the cell's index, A = the bucket (a frame's low byte)
file_cell:
        push    af
        ld      hl, FILED
        add     hl, de
        pop     af
        ld      (hl), a                 ; which bucket this cell is now in
        call    head_addr               ; HL = that frame's bucket
        ld      a, (hl)                 ; the chain it holds now becomes
        ld      c, a                    ; this cell's link
        inc     h
        ld      a, (hl)
        ld      b, a
        dec     h
        ld      a, e
        ld      (hl), a                 ; and the cell becomes the head
        inc     h
        ld      a, d
        ld      (hl), a

        ld      hl, LINK_LO
        add     hl, de
        ld      (hl), c
        ld      hl, LINK_HI
        add     hl, de
        ld      (hl), b
        ret

; When a cell next changes the level it shows.
;
; The charge falls by one a frame (half that for a wall), so a cell written with
; charge `c` at frame `w` drops below the lit threshold at `w + (c - threshold)`
; and reaches nothing at `w + c` -- doubled, less one, for a wall. Whichever of
; those is still ahead is the answer.
;
; in:  B = cy, C = cx ; out: HL = the frame
; **It must be the *next* change, not the first one**, and that is the whole
; subtlety. A cell written lit has two changes ahead of it -- down to remembered,
; then out -- and after the first has happened the answer is the second.
;
; The first cut read only the stored charge, so a wall that had just gone dim was
; re-filed for the frame it went dim on: a frame already past, whose bucket will
; not come round again inside the run. The wall stayed dim for ever and the
; 400-frame comparison caught it.
;
; So the current charge decides which transition is still ahead, and the stored
; charge and the write frame say when it falls due.
;
; in:  B = cy, C = cx ; out: HL = the frame, or `$FFFF` for never again
next_change:
        push    bc
        call    chg_addr
        ld      a, (hl)
        ld      (stored), a
        ld      a, h                    ; the journal, three pages up
        add     a, (WHEN - CHARGE) >> 8
        ld      h, a
        ld      e, (hl)
        inc     h
        ld      d, (hl)                 ; DE = the frame it was written at
        pop     bc
        push    de

        push    bc
        call    charge_at               ; what it is showing *now*
        pop     bc
        or      a
        jr      z, .never               ; already out: nothing more will happen
        cp      LIT_THRESHOLD + 1
        jr      c, .to_dark             ; already remembered: next stop is out

        ld      a, (stored)             ; still lit: next stop is remembered
        sub     LIT_THRESHOLD
        jr      .span
.to_dark:
        ld      a, (stored)
.span:  ld      e, a
        ld      d, 0                    ; DE = charge to burn through

        push    bc
        call    idx_addr                ; a wall burns it at half rate
        ld      a, (hl)
        pop     bc
        cp      32
        jr      nc, .add
        ex      de, hl
        add     hl, hl                  ; twice as many frames...
        dec     hl                      ; ...less one, which is the `ceil`
        ex      de, hl

.add:   pop     hl                      ; the frame it was written at
        add     hl, de
        ret

.never: pop     hl                      ; nothing is scheduled for a dark cell;
        ld      hl, $FFFF               ; the beam writing it is what wakes it
        ret

; Where a frame's bucket head lives: the low bytes page-aligned, the high bytes
; the page after, so `inc h` steps between them.
;
; in:  A = the frame, low byte ; out: HL = the head's low byte
head_addr:
        ld      l, a
        ld      h, HEAD_LO >> 8
        ret

; The cell's index, from its coordinates and back again. `cy * 32 + cx`, which
; is five doublings -- cheap enough at twice a frame per changed cell.
;
; in:  B = cy, C = cx ; out: DE = the index
cell_index:
        ld      h, 0
        ld      l, b
        add     hl, hl
        add     hl, hl
        add     hl, hl
        add     hl, hl
        add     hl, hl
        ld      a, l
        add     a, c
        ld      e, a
        ld      d, h
        ret

; in:  BC = the index (B high, C low) ; out: B = cy, C = cx
cell_of:
        ld      a, c
        and     COLS - 1
        ld      l, a                    ; cx
        ld      a, c
        and     ~(COLS - 1) & $FF
        ld      c, a
        ld      a, b
        ; cy = index >> 5, and the index is at most 703 so the high byte is at
        ; most 2: five shifts of a sixteen-bit value, done as three of the high
        ; byte folded in.
        ld      h, a
        ld      a, c
        rlca
        rlca
        rlca
        ld      c, a
        ld      a, h
        rlca
        rlca
        rlca
        and     %11111000
        or      c
        ld      b, a                    ; cy
        ld      c, l
        ret

; Everything filed, emptied. Called on arrival, when nothing is drawn and
; nothing is due.
clear_schedule:
        ld      hl, HEAD_LO
        ld      de, HEAD_LO + 1
        ld      bc, 512 - 1
        ld      (hl), $FF
        ldir
        ld      hl, DUE_LO
        ld      de, DUE_LO + 1
        ld      bc, 2 * COLS * PLAY_ROWS - 1
        ld      (hl), $FF
        ldir
        ld      hl, FILED
        ld      de, FILED + 1
        ld      bc, COLS * PLAY_ROWS - 1
        ld      (hl), $FF
        ldir
        ret

; in:  B = cy, C = cx ; out: HL = the cell's byte in `SHOWN`
shown_addr:
        ld      a, b
        add     a, a
        add     a, SHOWN_ROW & $FF
        ld      l, a
        ld      h, SHOWN_ROW >> 8
        ld      a, (hl)
        inc     l
        ld      h, (hl)
        add     a, c
        ld      l, a
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

; --- the light field -------------------------------------------------------
;
; One byte of charge a cell. A source tops a cell up; the charge falls by one a
; frame; what the cell *shows* is a threshold on it -- above `LIT_THRESHOLD`
; lit, above nought dim, else dark and invisible.
;
; **The fade is a ledger and not a pass** (issue #155, and the prototype's #148).
; Measured on this simulator, decaying all 704 cells costs **40,857 T-states a
; frame -- 124% of `ENTITY_CEILING`** before a single cell is drawn, and through
; a translate table it is worse at 45,388, because `ex de,hl` twice a cell costs
; more than the jump it saves. A counter costs **48**.
;
; So the charge is **not stored decayed**. `DECAYS` counts frames; a cell's
; stored charge is what it was when last written, and its charge *now* is
; `stored - (DECAYS - written_at)`, floored at nought. One byte a cell records
; the `DECAYS` it was written at, which is the journal -- the prototype keeps a
; sparse dict and the Z80 keeps a parallel array, because 704 bytes is cheaper
; here than a lookup.

; One frame of light: the ledger ticks, then every source writes.
light_frame:
        call    fade_tick
        call    beam_emit
        ret

; **The whole of the fade's per-frame cost.** Measured on this simulator,
; decaying all 704 cells costs 40,857 T-states a frame -- 124% of
; `ENTITY_CEILING` -- and through a translate table 45,388, because `ex de,hl`
; twice a cell is dearer than the jump it saves. This is 48.
fade_tick:
        ld      hl, (DECAYS)
        inc     hl
        ld      (DECAYS), hl
        ret

; What a cell is **showing**, which is not the same as what it remembers.
;
; `LightField` keeps the two apart and says why: *"a searchlight is as bright as
; a spotlight and forgotten far sooner"*. So a cell under the beam reads LIT
; while the beam is on it, even though the charge it leaves behind is only
; `CHARGE_SWEEP` -- ten frames, a fifth of a second. The fade is the memory; the
; source is the present.
;
; So the level is the brighter of the two: what the charge says, and what a
; source is putting there this frame. **A cell is lit now exactly when its
; stamp is this frame**, which needs no second array and no clearing pass.
;
; in:  B = cy, C = cx ; out: A = DARK, DIM or LIT. BC survives.
level_at:
        push    de
        call    charge_at               ; A = the remembered charge
        or      a
        jr      z, .dark                ; **no charge, so nothing is on it**
        ld      l, a
        ld      h, LEVEL_OF >> 8
        ld      a, (hl)                 ; ...as a level
        ld      e, a
        call    lit_now                 ; is a source on it this frame?
        jr      z, .done
        ld      a, LIT                  ; the beam's own level
        cp      e
        jr      nc, .out                ; brightest wins; nothing sums
.done:  ld      a, e
.out:   pop     de
        ret

        ; A source that writes a cell always leaves it some charge, so a cell
        ; with none cannot be lit now and the stamp need not be consulted.
        ;
        ; **Which is also what stops the room being born lit.** On arrival the
        ; frame counter is nought and every stamp is nought, so `lit_now`
        ; matched on all 704 cells and `enter_room` drew the whole room bright
        ; -- an unlit room, fully visible, which is the opposite of the game.
.dark:  pop     de
        xor     a
        ret

; Z if no source wrote this cell this frame, NZ if one did.
;
; in:  B = cy, C = cx ; out: flags. BC survives, HL and A do not.
lit_now:
        push    de
        call    when_addr               ; HL = the cell's 16-bit stamp
        ld      e, (hl)
        inc     h                       ; the high byte is a page on
        ld      d, (hl)
        ld      hl, (DECAYS)
        ld      a, e
        cp      l
        jr      nz, .no
        ld      a, d
        cp      h
        jr      nz, .no
        pop     de
        ld      a, 1
        and     a                       ; NZ: written this very frame
        ret
.no:    pop     de
        xor     a                       ; Z
        ret

; in:  B = cy, C = cx ; out: A = the charge now, 0 if it has run out
;
; **A wall fades at half rate** (`fade: 2`, which is how Levels 1 to 6 ship):
; three seconds of wall memory becomes six, because a swept wall is how a room
; is known. The prototype does it by adding a charge back on even frames --
; `linger`, and the `_bumps` counters #148 needed to stop a cell reviving after
; it died at the dip.
;
; **Here it is a shift, and the dip cannot happen.** Nothing is ever added
; back: the charge is a monotone function of elapsed frames, so
;
;     floor:  charge = stored - elapsed
;     wall:   charge = stored - ((elapsed + 1) >> 1)
;
; Verified against `LightField` with `linger` running, cell for cell, over 0 to
; 300 frames -- the `+ 1` is what makes it `ceil` and matches exactly.
;
; **The stamp is sixteen bits and has to be.** A wall holds `CHARGE_WALL` at
; half rate, which is **300 frames** -- longer than a byte -- so a one-byte
; stamp made a cell written 256 frames ago read as written this instant, at full
; charge. Walls would have flickered back to life once every five seconds.
charge_at:
        push    de
        call    chg_addr                ; HL = the cell's charge byte
        call    charge_from
        pop     de
        ret

; The same, given the address instead of the coordinates -- which is what lets
; `beam_emit` walk a row with one pointer (issue #156).
;
; in:  HL = &CHARGE[cell] ; out: A = the charge now. HL and DE are spent.
; **BC must survive.** `write_charge` keeps the charge it means to write in C,
; and `level_at` needs the cell's coordinates in BC afterwards for `lit_now` --
; so the first cut of this, which used C as a scratch for the index, broke the
; picture on 26 of 31 frame counts. The index is read *before* the stamp and
; carried on the stack instead.
charge_from:
        ld      a, (hl)
        or      a
        ret     z                       ; never written, or already run out
        push    af                      ; the stored charge

        ; Three pages below the charge is the index cache. **Is this a wall?** A
        ; wall's entry is a doubled mask, 0 to 30, and floor's is 32 to 62, so
        ; solidity is a byte read and not a 292 T-state `is_solid`.
        ld      a, h
        sub     (CHARGE - IDX) >> 8
        ld      h, a
        ld      a, (hl)
        push    af                      ; ...which rule applies

        ld      a, h                    ; up to the journal
        add     a, ((CHARGE - IDX) >> 8) + ((WHEN - CHARGE) >> 8)
        ld      h, a
        ld      e, (hl)
        inc     h
        ld      d, (hl)                 ; DE = the frame it was written at

        ld      hl, (DECAYS)
        ld      a, l
        sub     e
        ld      e, a
        ld      a, h
        sbc     a, d
        ld      d, a                    ; DE = frames since, sixteen bits

        pop     af                      ; the index again
        cp      32
        jr      nc, .fall               ; floor: the whole elapsed time
        inc     de                      ; wall: (elapsed + 1) >> 1
        srl     d
        rr      e

.fall:  ld      a, d
        or      a
        jr      nz, .gone               ; 256 frames or more: nothing survives
        pop     af                      ; the stored charge
        sub     e
        ret     nc
        xor     a                       ; it has faded out
        ret
.gone:  pop     af
        xor     a
        ret

; Where a cell's 16-bit write stamp lives: the low bytes a page-aligned block
; after the charge, the high bytes the page after that, so `inc h` steps from
; one to the other.
;
; in:  B = cy, C = cx ; out: HL = the low byte. BC survives, DE does not.
when_addr:
        call    chg_addr
        ld      a, h
        add     a, (WHEN - CHARGE) >> 8
        ld      h, a
        ret

; Top a cell up. **Brightest wins and nothing sums** -- a cell already showing
; more than this keeps it, which is `LightField.add`'s rule.
;
; in:  B = cy, C = cx, A = the charge to write
add_light:
        push    de
        push    af
        call    chg_addr
        pop     af
        call    write_charge
        pop     de
        ret

; Where a cell's charge lives. Page-aligned like the index cache, so a row's
; low byte is a multiple of 32 and adding `cx` cannot carry.
;
; in:  B = cy, C = cx ; out: HL = the byte. BC survives, DE does not.
chg_addr:
        ld      a, b
        add     a, a
        add     a, CHG_ROW & $FF
        ld      l, a
        ld      h, CHG_ROW >> 8
        ld      a, (hl)
        inc     l
        ld      h, (hl)
        add     a, c
        ld      l, a
        ret

; The beam, writing its disc into the field.
;
; **Its position is an input, not something this computes** (issue #155): the
; beam's motion comes from the run's xorshift and the station order, which is a
; slice of its own. `BEAM_X`/`BEAM_Y` are written from outside -- by the test,
; and by the beam's own code when it exists.
;
; A solid cell takes `CHARGE_WALL` and a floor cell `CHARGE_SWEEP`: the ground
; behind the beam goes out in a fifth of a second so the beam reads as a hole
; punched through the dark, but **the wall it passed is known for the whole
; fade**, which with no torch is the only way a room is known.
; **One address a row, not five a cell** (issue #156). It was 688 T-states a
; cell: `add_light` derived the charge's address, the journal's and the index
; cache's separately, each from `cy` and `cx`, and `charge_at` derived all three
; again to answer what the cell was showing.
;
; The disc is walked in rows, so within a row every one of those addresses
; advances by exactly one byte. And they are a fixed number of **pages** apart
; -- the index cache three below the charge, the journal three and four above --
; so one pointer serves all four with `ld a,h / add a,n / ld h,a`.
beam_emit:
        ld      a, (BEAM_Y)
        sub     BEAM_RADIUS
        ld      b, a                    ; cy of the disc's top row
        ld      ix, DISC                ; the half-width of each row
        ld      a, BEAM_RADIUS * 2 + 1
        ld      (rows_left), a
.row:   ld      a, (BEAM_X)
        sub     (ix+0)
        ld      c, a                    ; cx of this row's left end
        ld      a, (ix+0)
        add     a, a
        inc     a
        ld      (cells_left), a
        push    bc
        call    chg_addr                ; once for the whole row
        pop     bc

.cell:  push    hl
        ; Solidity from the index cache, three pages below the charge. A wall's
        ; entry is a doubled mask (0 to 30) and floor's is 32 to 62, so this is
        ; a byte read where `is_solid` is 292 T-states.
        ld      a, h
        sub     (CHARGE - IDX) >> 8
        ld      h, a
        ld      a, (hl)
        cp      32
        ld      a, CHARGE_SWEEP
        jr      nc, .got
        ld      a, CHARGE_WALL
.got:   pop     hl
        call    write_charge            ; HL = the charge byte, A = the charge
        inc     l                       ; the next cell of this row
        ld      a, (cells_left)
        dec     a
        ld      (cells_left), a
        jr      nz, .cell

        inc     b                       ; the next row of the disc
        inc     ix
        ld      a, (rows_left)
        dec     a
        ld      (rows_left), a
        jr      nz, .row
        ret

; Top a cell up, given its charge byte's address rather than its coordinates.
;
; **Brightest wins and nothing sums**, which is `LightField.add`'s rule: a cell
; already showing more than this keeps it. The check is kept even though the beam
; always wins today -- a floor cell holds at most `CHARGE_SWEEP` and the beam
; writes `CHARGE_SWEEP` -- because the player's glow and the room's lights are
; sources too, and one of them putting `CHARGE_LIT` on a floor cell must not be
; erased by the beam passing over it.
;
; in:  HL = &CHARGE[cell], A = the charge to write
; out: HL unchanged. BC survives.
write_charge:
        push    bc
        ld      c, a                    ; the charge we mean to write
        ld      b, (hl)                 ; what is stored there now
        inc     b
        dec     b
        jr      z, .write               ; nothing there: write
        ; **A cheap sufficient test, then the exact one.** The charge a cell is
        ; showing can only be less than what was stored in it -- decay takes it
        ; down and nothing puts it back -- so if this write beats the *stored*
        ; value it certainly beats the current one, and the expensive
        ; computation can be skipped.
        ;
        ; Which it always does today: a floor cell holds at most `CHARGE_SWEEP`
        ; and the beam writes `CHARGE_SWEEP`; a wall holds at most `CHARGE_WALL`
        ; and the beam writes that. So this is the path taken 37 times a frame,
        ; and it saves running `charge_from` on every one of them. The exact
        ; comparison is still here for the sources that have not arrived yet --
        ; the player's glow, the room's own lights -- one of which may well hold
        ; a cell brighter than the beam does.
        ld      a, c
        cp      b
        jr      nc, .write              ; beats what was stored: write
        push    hl
        call    charge_from             ; A = what it is showing *now*
        pop     hl
        cp      c
        jr      z, .write
        jr      nc, .done               ; it is brighter already: leave it
.write: ld      (hl), c
        push    hl
        ld      a, h                    ; the journal, three pages up
        add     a, (WHEN - CHARGE) >> 8
        ld      h, a
        ld      a, (DECAYS)
        ld      (hl), a
        inc     h
        ld      a, (DECAYS + 1)
        ld      (hl), a
        pop     hl
        ; **A write changes the cell now**, and the level needs no working out:
        ; a cell a source has just written reads `LIT`, because the level is the
        ; brighter of the charge's and the source's and this source is `LIT`. So
        ; this is a byte compare where `check_cell` would run `level_at` whole.
        ;
        ; `SHOWN` is nine pages above the charge, so the cell's own coordinates
        ; are not needed either -- they are worked out only in the rare branch
        ; that actually draws.
        push    hl
        ld      a, h
        add     a, (SHOWN - CHARGE) >> 8
        ld      h, a
        ld      a, (hl)
        cp      LIT
        jr      z, .drawn
        ld      (hl), LIT
        pop     hl
        push    hl
        push    bc
        call    addr_cell               ; B = cy, C = cx, only when drawing
        ld      a, LIT
        call    draw_at
        pop     bc
.drawn: pop     hl
        ; **Nothing is scheduled while the beam is still on the cell.** Its
        ; level is `LIT` whatever the charge says, so a due frame computed now
        ; would be recomputed next frame and the frame after -- 37 cells' worth
        ; of arithmetic, every frame, to answer a question that only matters
        ; once the beam has gone. `beam_edges` schedules the cells it leaves
        ; behind, which is seven of them once every six frames at `pace: 6`.
.done:  pop     bc
        ret

; The coordinates of the cell a charge address belongs to -- the inverse of
; `chg_addr`, for the row walk, which has the address and not the pair.
;
; in:  HL = &CHARGE[cell] ; out: B = cy, C = cx
addr_cell:
        ld      a, h
        sub     CHARGE >> 8
        ld      b, a                    ; which page: 0, 1 or 2
        ld      c, l
        call    cell_of
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

        ; **Black on black, not the room's hue** (issue #155). A room nobody
        ; has lit is invisible, which is the whole premise: dark is an
        ; attribute of nought, and every cell the light reaches writes its own
        ; as it is drawn.
        ld      hl, ATTRS
        ld      de, ATTRS + 1
        ld      bc, COLS * PLAY_ROWS - 1
        ld      (hl), 0
        ldir
        ret

; --- the room ---------------------------------------------------------------
;
; For every cell: solid cells wear one of the sixteen wall tiles, chosen by
; their four neighbours; floor wears one of sixteen blocks chosen by position,
; `(cy & 3) * 4 + (cx & 3)`, which is `floor.py`'s rule and the reason the
; stipple does not tile visibly. **Each at the level it is showing** (issue
; #155), so a room with no light in it draws nothing at all.

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
; One cell of room, at the level it is showing (issue #155).
;
; **A dark cell draws nothing.** It would be invisible anyway -- dark is black
; ink on black paper -- so this is the same picture for less work, and
; `tiles.draw` says the port does it this way too. The cell is cleared, because
; what was there a frame ago may have been lit.
draw_cell:
        push    bc
        call    level_at
        pop     bc
        ; Fall through with A = the level, which `draw_at` is the entry for when
        ; the caller already knows it.
draw_at:
        or      a
        jr      nz, .seen
        push    bc
        call    attr_cell               ; black on black
        pop     bc
        call    cell_addr
        jp      clear_cell

.seen:  push    af                      ; the level chooses the table
        push    bc
        call    attr_cell
        pop     bc
        pop     af
        push    bc
        call    tile_of                 ; DE = the tile's eight bytes
        pop     bc
        call    cell_addr               ; HL = the cell, top pixel row
        call    blit_tile
        ret

; Eight rows of nothing, for a cell the light has left.
clear_cell:
        xor     a
        ld      (hl), a : inc h
        ld      (hl), a : inc h
        ld      (hl), a : inc h
        ld      (hl), a : inc h
        ld      (hl), a : inc h
        ld      (hl), a : inc h
        ld      (hl), a : inc h
        ld      (hl), a
        ret

; One cell's attribute, on the rule the prototype states in as many words:
;
;     **light decides brightness; the cell's contents decide hue.**
;
; Both are single-valued per cell, so exactly one thing chooses an attribute and
; clash stays impossible. Dark is black on black -- not merely dim but
; invisible -- so it is not the room's ink at all.
;
; in:  B = cy, C = cx, A = the level
attr_cell:
        ; **Keep the level on the stack, not in E.** `attr_addr` builds its
        ; address through DE, so a level stashed there is gone by the time it
        ; returns -- which painted every lit cell black and is the second
        ; register-clobber of this slice. The first was `cell_addr` in #154.
        push    af
        call    attr_addr               ; HL = the cell's attribute byte
        pop     af
        or      a
        jr      z, .dark
        dec     a
        jr      z, .dim
        ld      (hl), %01000000 | ROOM_INK      ; LIT: bright, the room's hue
        ret
.dim:   ld      (hl), ROOM_INK                  ; DIM: the hue, unbright
        ret
.dark:  ld      (hl), 0                         ; DARK: black on black
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
; in:  B = cy, C = cx, **A = the level** (DIM or LIT; dark draws nothing)
; out: DE = eight bytes of tile. **BC survives; HL and A do not.**
tile_of:
        ; Which table: lit now, or remembered. The index is the same either
        ; way -- that is the whole reason #154 cached an index and not a
        ; pointer -- so this is one byte of page.
        cp      LIT
        ld      a, TILES_LIT >> 8
        jr      z, .table
        ld      a, TILES_DIM >> 8
.table: ld      (tile_page), a

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
        ld      a, (tile_page)          ; ...and the table is page-aligned too,
        ld      h, a                    ; so the index *is* the low byte
        ld      e, (hl)
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

; ...and of the charge. The journal sits a fixed `WHEN - CHARGE` after it, so
; one address serves both.
        ALIGN 64
CHG_ROW:
cy = 0
        DUP PLAY_ROWS
        DEFW CHARGE + cy * COLS
cy = cy + 1
        EDUP

; ...and of the level each cell was last drawn at.
        ALIGN 64
SHOWN_ROW:
cy = 0
        DUP PLAY_ROWS
        DEFW SHOWN + cy * COLS
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
TILES_LIT:
        DEFW WALL_LIT_00, WALL_LIT_01, WALL_LIT_02, WALL_LIT_03
        DEFW WALL_LIT_04, WALL_LIT_05, WALL_LIT_06, WALL_LIT_07
        DEFW WALL_LIT_08, WALL_LIT_09, WALL_LIT_10, WALL_LIT_11
        DEFW WALL_LIT_12, WALL_LIT_13, WALL_LIT_14, WALL_LIT_15
        DEFW FLOOR_LIT_00, FLOOR_LIT_01, FLOOR_LIT_02, FLOOR_LIT_03
        DEFW FLOOR_LIT_04, FLOOR_LIT_05, FLOOR_LIT_06, FLOOR_LIT_07
        DEFW FLOOR_LIT_08, FLOOR_LIT_09, FLOOR_LIT_10, FLOOR_LIT_11
        DEFW FLOOR_LIT_12, FLOOR_LIT_13, FLOOR_LIT_14, FLOOR_LIT_15

; A cell the light has left but the player still remembers: the wall's outline
; with its courses dotted, and no stipple on the floor at all. Same indices,
; different table -- which is what the index cache buys.
        ALIGN 256
TILES_DIM:
        DEFW WALL_DIM_00, WALL_DIM_01, WALL_DIM_02, WALL_DIM_03
        DEFW WALL_DIM_04, WALL_DIM_05, WALL_DIM_06, WALL_DIM_07
        DEFW WALL_DIM_08, WALL_DIM_09, WALL_DIM_10, WALL_DIM_11
        DEFW WALL_DIM_12, WALL_DIM_13, WALL_DIM_14, WALL_DIM_15
        DEFW FLOOR_DIM_00, FLOOR_DIM_01, FLOOR_DIM_02, FLOOR_DIM_03
        DEFW FLOOR_DIM_04, FLOOR_DIM_05, FLOOR_DIM_06, FLOOR_DIM_07
        DEFW FLOOR_DIM_08, FLOOR_DIM_09, FLOOR_DIM_10, FLOOR_DIM_11
        DEFW FLOOR_DIM_12, FLOOR_DIM_13, FLOOR_DIM_14, FLOOR_DIM_15

; charge -> level, as the prototype's `_LEVEL_OF`: above the threshold lit,
; above nought dim, else dark. A table, because a Z80 compares no faster than
; it indexes.
        ALIGN 256
LEVEL_OF:
c = 0
        DUP 256
        ; **The sum of two comparisons, negated.** Nought is dark, up to the
        ; threshold is dim, over it is lit -- so the two comparisons give the
        ; three levels with no conditional at all.
        ;
        ; The negation is not decoration: **sjasmplus's comparisons yield −1 for
        ; true**, not 1, so the unnegated sum built a table of 0, 255, 254 and
        ; every lit cell read as a level nothing recognised. The suite now
        ; compares this table against the prototype's `_LEVEL_OF` byte for byte,
        ; because a table that is wrong in the same way everywhere is invisible
        ; in a picture until you look for it.
        DEFB -((c > LIT_THRESHOLD) + (c > 0))
c = c + 1
        EDUP

; The beam's disc: a half-width a row. `3 5 7 7 7 5 3` is 37 cells, and the
; prototype's `disc_widths` says why -- it is the one set a drawn circle agrees
; with cell for cell.
DISC:   DEFB 1, 2, 3, 3, 3, 2, 1

; --- state ------------------------------------------------------------------

mask_acc:   DEFB 0
rows_left:  DEFB 0          ; `beam_emit`'s counters, in memory because the
cells_left: DEFB 0          ; row walk needs every register pair it has
disc_x:     DEFB 0          ; which disc `check_disc` is walking
disc_y:     DEFB 0
disc_rows:  DEFB 0
disc_cells: DEFB 0
sched_at:   DEFW 0          ; the frame `reschedule` is filing under
stored:     DEFB 0          ; the charge `next_change` is reasoning about

; Where the beam was last frame, so `beam_edges` can tell whether it moved.
; Starts on the beam's own cell, so the first frame finds no edges and the
; disc is drawn by `beam_emit` and the schedule alone.
WAS_BEAM:   DEFB 6, 5
player_cx:  DEFB PLAYER_CX
player_cy:  DEFB PLAYER_CY
tile_page:  DEFB 0          ; which tile table this cell reads, lit or dim

; The frames that have passed, which is the whole of the fade's per-frame cost.
; Two bytes so it does not wrap inside a room, though only the low byte is
; compared: nothing outlives `FADE_FRAMES`, which is under 256.
DECAYS:     DEFW 0

; Where the beam is, in cells. **Written from outside this slice** (issue
; #155): its motion is the run's xorshift and the station order, and that is a
; slice of its own.
BEAM_X:     DEFB 6
BEAM_Y:     DEFB 5

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

; The charge a cell holds, and the frame each was written at -- the journal.
; Page-aligned for the same reason the index cache is, and `WHEN` a whole number
; of pages after `CHARGE` so `chg_addr` serves both with one add.
; The charge a cell holds, the frame each was written at -- the journal, two
; bytes a cell and a page apart so `inc h` reaches the high byte -- and the level
; each was last drawn at. All page-aligned, for the same reason the index cache
; is: a row's low byte is a multiple of 32, so adding `cx` cannot carry.
CHARGE: EQU (IDX_END + 255) & $FF00
WHEN:   EQU CHARGE + 768
SHOWN:  EQU WHEN + 1536
; The schedule (issue #156): each frame's bucket head, and each cell's due
; frame and link. `$FF` throughout means nil, which is why `clear_schedule`
; fills with it.
HEAD_LO: EQU (SHOWN + COLS * PLAY_ROWS + 255) & $FF00
HEAD_HI: EQU HEAD_LO + 256
DUE_LO:  EQU HEAD_HI + 256
DUE_HI:  EQU DUE_LO + COLS * PLAY_ROWS
LINK_LO: EQU DUE_HI + COLS * PLAY_ROWS
LINK_HI: EQU LINK_LO + COLS * PLAY_ROWS
; Which bucket a cell is filed in, or `$FF` for none -- what keeps a cell from
; being filed twice and orphaning the chain behind it.
FILED:   EQU LINK_HI + COLS * PLAY_ROWS
FIELD_END: EQU FILED + COLS * PLAY_ROWS
