CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -fPIC
UNAME := $(shell uname)
ifeq ($(UNAME),Darwin)
  LIB := build/libtgtb.dylib
  SHARED := -dynamiclib
else
  LIB := build/libtgtb.so
  SHARED := -shared
endif

all: $(LIB)

$(LIB): src/engine.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) $(SHARED) -o $@ $<

clean:
	rm -rf build

.PHONY: all clean
