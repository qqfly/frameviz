#include <frameviz/client.hpp>
#include <iostream>
#include <string_view>
int main(int argc, char** argv) {
    const bool hold = argc == 3 && std::string_view(argv[2]) == "--hold";
    if (argc != 2 && !hold) return 2;
    try {
        frameviz::FrameVizClient client(argv[1]);
        client.connect(std::chrono::seconds(2));
        std::cout << "connected" << std::endl;
        if (hold) std::cin.get();
        client.close();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
