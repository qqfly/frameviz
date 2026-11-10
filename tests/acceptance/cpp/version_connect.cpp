#include <frameviz/client.hpp>
#include <iostream>
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    try {
        frameviz::FrameVizClient client(argv[1]);
        client.connect(std::chrono::seconds(2));
        client.close();
        std::cout << "connected\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
