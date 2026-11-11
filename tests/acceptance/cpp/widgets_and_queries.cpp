#include <frameviz/viz.hpp>

#include <atomic>
#include <chrono>
#include <future>
#include <iostream>
#include <stdexcept>

using namespace frameviz;
using namespace std::chrono_literals;

void require(bool condition, const char *message) {
  if (!condition) throw std::runtime_error(message);
}

int main(int argc, char **argv) {
  if (argc != 3 && argc != 4) return 2;
  try {
    auto viz = Viz::connect(argv[1], argv[2]);
    if (argc == 4) {
      const bool expectedOnline = std::string(argv[3]) == "online";
      std::cout << "connected" << std::endl;
      std::string ready;
      std::getline(std::cin, ready);
      require(viz->waitForViewer(0s) == expectedOnline, "Readiness does not match current Viewer connection");
      if (expectedOnline) {
        require(viz->waitForViewer(0s), "Readiness was consumed by the first wait");
      }
      require(viz->waitForEvent("viewer_ready", 1s).has_value(), "Ordinary wait lost unread history");
      require(!viz->waitForEvent("viewer_ready", 0s).has_value(), "Ordinary wait did not consume the event");
      return 0;
    }
    auto box = viz->addBox();
    auto slider = viz->addWidget("number", "Box X", 0, {{"minimum", -3}, {"maximum", 3}});
    std::atomic<int> obsolete{0};
    std::promise<float> moved;
    auto result = moved.get_future();
    viz->onWidgetChange(slider, [&](const json &) { ++obsolete; });
    viz->onWidgetChange(slider, [&](const json &event) {
      const auto x = event.at("value").get<float>();
      viz->setTransform(box, RigidPose{{x, 0, 0}});
    });
    viz->onWidgetChange(slider, [&](const json &) {
      auto state = viz->getDisplayState(true);
      moved.set_value(state.at("objects").at(0).at("world_transform").at("position").at(0).get<float>());
    }, true);
    viz->setWidgetValue(slider, 1.0);
    require(result.wait_for(150ms) == std::future_status::timeout, "Silent write triggered handler");
    viz->setWidgetValue(slider, 2.5, true);
    require(result.wait_for(3s) == std::future_status::ready && result.get() == 2.5f,
            "Automatic callback did not complete its nested SDK calls");
    require(obsolete == 0, "Replaced widget handler ran");
    require(viz->getWidgetValue(slider) == 2.5 && viz->listWidgets().size() == 1,
            "Widget read does not match the committed value");
    auto automatic = viz->waitForEvent("widget_changed", 1s);
    require(automatic && automatic->at("value") == 2.5, "Automatic wait missed committed event");

    viz->offWidgetChange(slider);
    auto manual = Viz::connect(argv[1], argv[2], 2s, false);
    int calls = 0;
    manual->onWidgetChange(slider, [&](const json &) { ++calls; });
    manual->setWidgetValue(slider, 2.0, true);
    require(manual->waitForEvent("widget_changed", 2s).has_value() && calls == 0,
            "Manual callback ran before polling");
    manual->pollEvents();
    require(calls == 1, "Manual poll did not dispatch the widget event");
    viz->removeWidget(slider);
    require(viz->listWidgets().empty(), "Widget removal did not persist");
    const auto camera = viz->getCameraView();
    const auto closer = viz->addWidget("button", "Close SDK connection");
    std::promise<void> closed;
    auto closeResult = closed.get_future();
    viz->onWidgetChange(closer, [&](const json &) {
      viz->close();
      closed.set_value();
    });
    viz->setWidgetValue(closer, nullptr, true);
    require(closeResult.wait_for(3s) == std::future_status::ready,
            "Closing from an automatic callback stalled");
    manual->removeWidget(closer);
    std::cout << camera.dump() << '\n';
    return 0;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
