#include <frameviz/host.hpp>
#include <iostream>
int main() { auto path = frameviz::findHostExecutable(); std::cout << path.value_or("NONE") << "\n"; }
