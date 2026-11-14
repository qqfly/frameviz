#include <frameviz/host.hpp>
#include <iostream>
int main() {
    try {
        auto path = frameviz::findHostExecutable();
        std::cout << path.value_or("NONE") << '\n';
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
