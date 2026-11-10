#include <frameviz/client.hpp>
#include <iostream>
int main(int argc, char** argv) {
    if (argc != 4) return 2;
    try {
        frameviz::FrameVizClient client(argv[1]);
        client.connect(std::chrono::seconds(2));
        std::cout << client.presentView(argv[2], argv[3]) << '\n';
        client.close();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
