#include "kernel.hpp"

#include <iostream>
#include <iterator>

int main() {
  try {
    const std::string input(std::istreambuf_iterator<char>(std::cin), {});
    std::cout << r2s::kinematic::integrate_text(input);
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "r2s-kinematic-cli: " << error.what() << '\n';
    return 2;
  }
}
