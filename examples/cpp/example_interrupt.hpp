#pragma once

#include <atomic>
#include <cerrno>
#include <csignal>
#include <iostream>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <conio.h>
#include <chrono>
#include <thread>
#else
#include <poll.h>
#include <unistd.h>
#endif

namespace frameviz::example {

// Only the command-line examples own SIGINT. Close views on the main thread.
class Interrupt {
public:
#ifdef _WIN32
    Interrupt() { SetConsoleCtrlHandler(requestStop, TRUE); }
    ~Interrupt() { SetConsoleCtrlHandler(requestStop, FALSE); }
#else
    Interrupt() : previous(std::signal(SIGINT, requestStop)) {}
    ~Interrupt() {
        if (previous != SIG_ERR) std::signal(SIGINT, previous);
    }
#endif
    Interrupt(const Interrupt &) = delete;
    Interrupt &operator=(const Interrupt &) = delete;

    bool requested() const { return interrupted.load(std::memory_order_relaxed); }

    template <typename... Views>
    bool waitForEnter(Views &...views) const {
        std::cout << std::flush;
        waitForInput();
        if (!requested()) return true;
        (views.close(), ...);
        return false;
    }

private:
    static_assert(std::atomic<bool>::is_always_lock_free);
    static inline std::atomic<bool> interrupted{false};
#ifdef _WIN32
    static BOOL WINAPI requestStop(DWORD event) {
        if (event != CTRL_C_EVENT && event != CTRL_BREAK_EVENT) return FALSE;
        interrupted.store(true, std::memory_order_relaxed);
        return TRUE;
    }
#else
    static void requestStop(int) { interrupted.store(true, std::memory_order_relaxed); }
    void (*previous)(int);
#endif

    void waitForInput() const {
#ifdef _WIN32
        const auto input = GetStdHandle(STD_INPUT_HANDLE);
        DWORD consoleMode = 0;
        const bool console = GetConsoleMode(input, &consoleMode);
        const bool pipe = GetFileType(input) == FILE_TYPE_PIPE;
        while (!requested()) {
            if (console) {
                if (_kbhit() && _getch() == '\r') return;
            } else {
                DWORD available = 0;
                if (pipe && !PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr)) return;
                if (!pipe || available != 0) {
                    std::cin.get();
                    return;
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
#else
        pollfd input{STDIN_FILENO, POLLIN, 0};
        while (!requested()) {
            const int ready = poll(&input, 1, 50);
            if (ready < 0 && errno != EINTR) return;
            if (ready > 0) {
                char key;
                if (read(STDIN_FILENO, &key, 1) >= 0 || errno != EINTR) return;
            }
        }
#endif
    }
};

}  // namespace frameviz::example
