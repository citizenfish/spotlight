# The port's build. One command, so the tests and a person run the same thing.
#
# sjasmplus is not in Homebrew and is built from source; see README.md for the
# clone and the submodule step, which is not optional. SJASMPLUS can point at
# it anywhere.
SJASMPLUS ?= $(HOME)/.local/bin/sjasmplus

BUILD := build
BIN   := $(BUILD)/spotlight.bin
TAP   := $(BUILD)/spotlight.tap

.PHONY: all tables clean

all: $(BIN)

$(BIN): src/main.asm src/rooms.asm src/bitmaps.asm | $(BUILD)
	cd src && $(SJASMPLUS) --sym=main.sym main.asm

$(BUILD):
	mkdir -p $(BUILD)

# The generated tables, from the authored text. Both are committed and both are
# regenerated and compared byte for byte by the suite, so this is here to make
# an art or level change one command rather than two remembered ones.
tables:
	cd .. && python tools/bitmaps.py \
	    --python prototype/spikes/bitmaps_gen.py \
	    --asm spectrum/src/bitmaps.asm assets/sprites assets/tiles
	cd .. && python tools/rooms.py assets/levels/ladder.txt dogleg \
	    --asm spectrum/src/rooms.asm

clean:
	rm -f $(BUILD)/* src/main.sym
