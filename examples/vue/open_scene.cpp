// Populate the same Vue embedding example from the C++ SDK.
#include <frameviz/discovery.hpp>
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>
#include <regex>

#ifdef _WIN32
#include <windows.h>
#include <shellapi.h>
#else
#include <spawn.h>
#include <sys/wait.h>
extern char **environ;
#endif

int main(int argc, char **argv) {
    const std::string page = argc == 2 ? argv[1] : "http://127.0.0.1:8000/embedded_viewer.html";
    if (argc > 2 || !std::regex_match(page, std::regex(R"(http://(127\.0\.0\.1|localhost|\[::1\])(:[0-9]+)?/[A-Za-z0-9_./-]+)"))) {
        std::cerr << "Usage: open_vue_scene [loopback HTTP page URL]\n";
        return 2;
    }
    try {
        const frameviz::example::Interrupt interrupt;
        auto viz = frameviz::Viz::open("", "Vue embedded scene", 800, 600, true, std::nullopt, 0);
        const auto host = frameviz::readDiscoveryFile();
        if (!host || host->token.empty() || !host->port) throw std::runtime_error("No local FrameViz discovery record");
        viz->setViewConfig({{"show_axes", false}, {"show_grid", false}, {"background", {1, 1, 1}}});
        viz->addBox({0.95f, 0.75f, 0.9f}, {-0.7f, 0, 0.45f}, {0, 0, 0, 1}, {0.2f, 0.5f, 0.87f});
        viz->addSphere(0.38f, {0.85f, 0, 0.38f}, {0, 0, 0, 1}, {0.95f, 0.62f, 0.18f});
        viz->setCameraPose({4, -6, 4}, {0, 0, 0.4f}, {0, 0, 1});
        // The fragment is read by the page and does not go to its HTTP server.
        std::string url = page + "?view_id=" + viz->viewId() + "&ws_port=" + std::to_string(host->port) + "#token=";
        constexpr char hex[] = "0123456789ABCDEF";
        for (unsigned char c : host->token) {
            url += '%';
            url += hex[c >> 4];
            url += hex[c & 15];
        }
#ifdef _WIN32
        if (reinterpret_cast<INT_PTR>(ShellExecuteA(nullptr, "open", url.c_str(), nullptr, nullptr, SW_SHOWNORMAL)) <= 32)
            throw std::runtime_error("Unable to open the Vue page");
#else
#ifdef __APPLE__
        const char *program = "open";
#else
        const char *program = "xdg-open";
#endif
        const char *args[] = {program, url.c_str(), nullptr};
        pid_t pid;
        int status;
        if (posix_spawnp(&pid, program, nullptr, nullptr, const_cast<char **>(args), environ) ||
            waitpid(pid, &status, 0) != pid || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
            throw std::runtime_error("Unable to open the Vue page");
        }
#endif
        std::cout << "Try Hide viewer / Show viewer. Enter to close the scene.\n";
        if (!interrupt.waitForEnter(*viz)) return 130;
        viz->close();
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
