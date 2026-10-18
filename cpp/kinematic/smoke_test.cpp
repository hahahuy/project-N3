#include "kernel.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void require(bool condition, const std::string& message) {
  if (!condition) throw std::runtime_error(message);
}
void close(double actual, double expected, const std::string& message) {
  if (std::abs(actual - expected) > 1e-12) throw std::runtime_error(message);
}
}

int main() {
  try {
    using r2s::kinematic::SourceState;
    using r2s::kinematic::State;
    const State initial{0.0, 0.0, 0.0, 0.0, 10.0};
    const std::vector<SourceState> source{{0, 100.0, 100.0}, {50'000, 2.0, 0.1}, {150'000, -4.0, 0.2}};
    const auto states = r2s::kinematic::integrate(initial, source, 0.05);
    require(states.size() == source.size(), "integration row count mismatch");
    close(states.front().time_s, 0.0, "initial time changed");
    close(states[1].time_s, 0.05, "first time mismatch");
    close(states[1].speed_mps, 10.1, "first speed mismatch");
    close(states[2].time_s, 0.10, "capped time mismatch");
    close(states[2].speed_mps, 9.9, "capped speed mismatch");
    const std::string output = r2s::kinematic::integrate_text("0 0 0 10 0.05 3\n0 100 100\n50000 2 0.1\n150000 -4 0.2\n");
    require(static_cast<std::size_t>(std::count(output.begin(), output.end(), '\n')) == source.size(), "text row count mismatch");
    std::cout << "r2s-kinematic-smoke: ok\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "r2s-kinematic-smoke: " << error.what() << '\n';
    return 1;
  }
}
