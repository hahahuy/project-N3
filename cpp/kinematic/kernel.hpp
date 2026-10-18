#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace r2s::kinematic {

struct SourceState {
  long long timestamp_us{};
  double acceleration_mps2{};
  double yaw_rate_radps{};
};

struct State {
  double time_s{};
  double x_m{};
  double y_m{};
  double yaw_rad{};
  double speed_mps{};
};

std::vector<State> integrate(const State& initial,
                             const std::vector<SourceState>& source,
                             double fixed_timestep_s = 0.05);

// Text format is intentionally tiny and shared by the native parity runner and
// the browser/WASM diagnostic: one initial state, then N source rows.
// Input:  x y yaw speed timestep N, followed by N rows: timestamp_us acc yaw_rate
// Output: one state row per source sample: time x y yaw speed
std::string integrate_text(const std::string& input);

}  // namespace r2s::kinematic
