#include "kernel.hpp"

#include <cmath>
#include <sstream>
#include <stdexcept>

namespace r2s::kinematic {

std::vector<State> integrate(const State& initial,
                             const std::vector<SourceState>& source,
                             double fixed_timestep_s) {
  if (!std::isfinite(fixed_timestep_s) || fixed_timestep_s <= 0.0) {
    throw std::invalid_argument("fixed_timestep_s must be finite and positive");
  }
  if (source.empty()) {
    throw std::invalid_argument("source must not be empty");
  }
  std::vector<State> states{initial};
  states.reserve(source.size() + 1);
  for (std::size_t index = 1; index < source.size(); ++index) {
    const auto& previous_measurement = source[index - 1];
    const auto& measurement = source[index];
    const double dt = std::min(
        fixed_timestep_s,
        std::max(0.0, static_cast<double>(measurement.timestamp_us - previous_measurement.timestamp_us) / 1'000'000.0));
    const State& previous = states.back();
    const double speed = previous.speed_mps + measurement.acceleration_mps2 * dt;
    const double yaw = previous.yaw_rad + measurement.yaw_rate_radps * dt;
    states.push_back({
        previous.time_s + dt,
        previous.x_m + speed * std::cos(yaw) * dt,
        previous.y_m + speed * std::sin(yaw) * dt,
        yaw,
        speed,
    });
  }
  return states;
}

std::string integrate_text(const std::string& input) {
  std::istringstream reader(input);
  State initial{};
  double timestep = 0.0;
  std::size_t count = 0;
  if (!(reader >> initial.x_m >> initial.y_m >> initial.yaw_rad >> initial.speed_mps >> timestep >> count)) {
    throw std::invalid_argument("invalid kinematic input header");
  }
  std::vector<SourceState> source;
  source.reserve(count);
  for (std::size_t index = 0; index < count; ++index) {
    SourceState item{};
    if (!(reader >> item.timestamp_us >> item.acceleration_mps2 >> item.yaw_rate_radps)) {
      throw std::invalid_argument("invalid kinematic source row");
    }
    source.push_back(item);
  }
  const auto states = integrate(initial, source, timestep);
  std::ostringstream output;
  output.precision(17);
  for (const auto& state : states) {
    output << state.time_s << ' ' << state.x_m << ' ' << state.y_m << ' '
           << state.yaw_rad << ' ' << state.speed_mps << '\n';
  }
  return output.str();
}

}  // namespace r2s::kinematic
