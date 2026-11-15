#include "frameviz/viz.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <system_error>

#ifdef _WIN32
#include <process.h>
#include <windows.h>
#else
#include <cerrno>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>
extern char **environ;
#endif

namespace frameviz {
namespace {

namespace fs = std::filesystem;

class CaptureDirectory {
public:
  CaptureDirectory() {
#ifdef _WIN32
    auto root = fs::temp_directory_path();
    wchar_t name[MAX_PATH];
    if (!GetTempFileNameW(root.c_str(), L"fvz", 0, name)) {
      throw std::runtime_error("Unable to create FrameViz capture directory");
    }
    fs::remove(name);
    if (!fs::create_directory(name)) {
      throw std::runtime_error("Unable to create FrameViz capture directory");
    }
    path = name;
#else
    auto name = (fs::temp_directory_path() / "frameviz-capture.XXXXXX").string();
    if (!mkdtemp(name.data())) {
      throw std::runtime_error("Unable to create FrameViz capture directory");
    }
    path = name;
#endif
  }
  ~CaptureDirectory() {
    std::error_code error;
    fs::remove_all(path, error);
  }
  fs::path path;
};

void runRenderer(const fs::path &directory) {
  const char *python = std::getenv("FRAMEVIZ_PYTHON");
  if (!python || !*python) {
#ifdef _WIN32
    python = "python";
#else
    python = "python3";
#endif
  }
#ifdef _WIN32
  // _wspawnvp does not quote arguments on its own.
  const auto executable = fs::u8path(python).wstring();
  const auto program = L"\"" + executable + L"\"";
  const auto request = L"\"" + directory.wstring() + L"\"";
  const wchar_t *args[] = {program.c_str(), L"-m", L"frameviz._capture_worker",
                           request.c_str(), nullptr};
  const bool ok = _wspawnvp(_P_WAIT, executable.c_str(), args) == 0;
#else
  auto request = directory.string();
  const char *args[] = {python, "-m", "frameviz._capture_worker", request.c_str(), nullptr};
  pid_t pid;
  const int spawnError = posix_spawnp(&pid, python, nullptr, nullptr,
                                     const_cast<char **>(args), environ);
  int status = 0;
  pid_t result = -1;
  if (spawnError == 0) {
    do {
      result = waitpid(pid, &status, 0);
    } while (result == -1 && errno == EINTR);
  }
  const bool ok = result > 0 && WIFEXITED(status) && WEXITSTATUS(status) == 0;
#endif
  if (!ok) {
    std::ifstream error(directory / "error.txt", std::ios::binary);
    std::string detail{std::istreambuf_iterator<char>(error), {}};
    if (!detail.empty()) throw std::runtime_error("FrameViz capture failed: " + detail);
    throw std::runtime_error(
        "Unable to start FrameViz capture. Set FRAMEVIZ_PYTHON to an interpreter "
        "with the matching FrameViz wheel and its [capture] extra.");
  }
}

std::vector<uint8_t> capture(const std::pair<std::string, std::string> &session,
                             const std::string &view, json request) {
  CaptureDirectory directory;
  request["url"] = session.first;
  request["token"] = session.second;
  request["view"] = view;
  {
    std::ofstream file(directory.path / "request.json", std::ios::binary);
    file.exceptions(std::ios::failbit | std::ios::badbit);
    file << request.dump();
    file.close();
  }

  runRenderer(directory.path);
  std::ifstream output(directory.path / "output", std::ios::binary);
  if (!output) throw std::runtime_error("FrameViz renderer did not produce an output file");
  return {std::istreambuf_iterator<char>(output), {}};
}

void writeOutput(const std::string &path, const std::vector<uint8_t> &bytes) {
  std::ofstream output(fs::u8path(path), std::ios::binary);
  output.exceptions(std::ios::failbit | std::ios::badbit);
  output.write(reinterpret_cast<const char *>(bytes.data()), bytes.size());
  output.close();
}

} // namespace

std::vector<uint8_t> Viz::screenshot(const std::string &path,
                                    const std::optional<json> &cameraView,
                                    const std::optional<int> &width,
                                    const std::optional<int> &height) {
  json request = {{"operation", "png"}};
  if (cameraView) request["camera_view"] = *cameraView;
  if (width) request["width"] = *width;
  if (height) request["height"] = *height;
  auto bytes = capture(m_client->captureSession(), m_viewId, std::move(request));
  if (!path.empty()) writeOutput(path, bytes);
  return bytes;
}

void Viz::exportHtml(const std::string &path, const json &animation) {
  if (path.empty()) throw std::invalid_argument("An HTML output path is required");
  auto bytes = capture(m_client->captureSession(), m_viewId,
                       {{"operation", "html"}, {"animation", animation}});
  writeOutput(path, bytes);
}

} // namespace frameviz
