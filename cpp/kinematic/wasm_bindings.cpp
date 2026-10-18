#include "kernel.hpp"

#include <emscripten/bind.h>

EMSCRIPTEN_BINDINGS(r2s_kinematic) {
  emscripten::function("integrateText", &r2s::kinematic::integrate_text);
}
