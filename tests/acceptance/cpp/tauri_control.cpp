#include <frameviz/tauri.hpp>
#include <iostream>
#include <string_view>

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    const auto action = std::string_view(argv[1]);
    const bool ok = action == "open" ? frameviz::tryOpenTauriWindow("v_test")
                                    : frameviz::tryCloseTauriWindow("v_test");
    std::cout << (ok ? "ok" : "failed") << '\n';
}
