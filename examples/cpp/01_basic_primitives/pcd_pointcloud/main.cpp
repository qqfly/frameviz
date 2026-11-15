/**
 * FrameViz C++ Example - PCD Point Cloud (ASCII)
 *
 * 对应 Python: examples/python/01_basic_primitives/use_pcd_pointcloud.py
 */

#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <cstring>
#include <algorithm>

using namespace frameviz;

static void decodePackedRgb(uint32_t packed, uint8_t &r, uint8_t &g, uint8_t &b)
{
    r = static_cast<uint8_t>((packed >> 16) & 0xFF);
    g = static_cast<uint8_t>((packed >> 8) & 0xFF);
    b = static_cast<uint8_t>(packed & 0xFF);
}

int main(int argc, char **argv)
{
    std::string path = "data/models/pointcloud/synthetic_cloud.pcd";
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--path" && i + 1 < argc) {
            path = argv[i + 1];
            ++i;
        } else if (arg == "--help" || arg == "-h") {
            std::cout << "Usage: pcd_pointcloud --path /path/to/file.pcd\n";
            return 0;
        }
    }

    if (path.empty()) {
        std::cerr << "Usage: pcd_pointcloud --path /path/to/file.pcd" << std::endl;
        return 1;
    }

    std::ifstream file(path);
    if (!file) {
        std::cerr << "Failed to open: " << path << std::endl;
        return 1;
    }

    std::vector<std::string> fields;
    std::vector<std::string> types;
    std::vector<int> counts;
    std::string data_type;

    std::string line;
    while (std::getline(file, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        std::istringstream iss(line);
        std::string key;
        iss >> key;
        if (key == "FIELDS") {
            fields.clear();
            std::string f;
            while (iss >> f) fields.push_back(f);
        } else if (key == "TYPE") {
            types.clear();
            std::string t;
            while (iss >> t) types.push_back(t);
        } else if (key == "COUNT") {
            counts.clear();
            int c;
            while (iss >> c) counts.push_back(c);
        } else if (key == "DATA") {
            iss >> data_type;
            break;
        }
    }

    if (data_type != "ascii") {
        std::cerr << "Only ASCII PCD supported in this example. DATA="
                  << data_type << std::endl;
        return 1;
    }

    int idx_x = -1, idx_y = -1, idx_z = -1;
    int idx_r = -1, idx_g = -1, idx_b = -1;
    int idx_rgb = -1, idx_rgba = -1;

    for (size_t i = 0; i < fields.size(); ++i) {
        if (fields[i] == "x")
            idx_x = static_cast<int>(i);
        else if (fields[i] == "y")
            idx_y = static_cast<int>(i);
        else if (fields[i] == "z")
            idx_z = static_cast<int>(i);
        else if (fields[i] == "r")
            idx_r = static_cast<int>(i);
        else if (fields[i] == "g")
            idx_g = static_cast<int>(i);
        else if (fields[i] == "b")
            idx_b = static_cast<int>(i);
        else if (fields[i] == "rgb")
            idx_rgb = static_cast<int>(i);
        else if (fields[i] == "rgba")
            idx_rgba = static_cast<int>(i);
    }

    if (idx_x < 0 || idx_y < 0 || idx_z < 0) {
        std::cerr << "PCD missing x/y/z fields." << std::endl;
        return 1;
    }

    std::vector<float> positions;
    std::vector<Color> colors;
    positions.reserve(300000);
    colors.reserve(300000);

    while (std::getline(file, line)) {
        if (line.empty()) continue;
        std::istringstream iss(line);
        std::vector<std::string> tokens;
        std::string token;
        while (iss >> token) tokens.push_back(token);
        if (tokens.size() < fields.size()) continue;

        float x = std::stof(tokens[idx_x]);
        float y = std::stof(tokens[idx_y]);
        float z = std::stof(tokens[idx_z]);

        uint8_t r = 200, g = 200, b = 200;
        if (idx_r >= 0 && idx_g >= 0 && idx_b >= 0) {
            float rf = std::stof(tokens[idx_r]);
            float gf = std::stof(tokens[idx_g]);
            float bf = std::stof(tokens[idx_b]);
            if (rf <= 1.0f && gf <= 1.0f && bf <= 1.0f) {
                r = static_cast<uint8_t>(rf * 255);
                g = static_cast<uint8_t>(gf * 255);
                b = static_cast<uint8_t>(bf * 255);
            } else {
                r = static_cast<uint8_t>(rf);
                g = static_cast<uint8_t>(gf);
                b = static_cast<uint8_t>(bf);
            }
        } else if (idx_rgb >= 0 || idx_rgba >= 0) {
            int idx = (idx_rgb >= 0) ? idx_rgb : idx_rgba;
            const std::string &v = tokens[idx];
            uint32_t packed = 0;
            if (v.find('.') != std::string::npos
                || v.find('e') != std::string::npos
                || v.find('E') != std::string::npos) {
                float f = std::stof(v);
                std::memcpy(&packed, &f, sizeof(uint32_t));
            } else {
                packed = static_cast<uint32_t>(std::stoul(v));
            }
            decodePackedRgb(packed, r, g, b);
        }

        // Use the sample coordinates as-is; scale here if your input uses millimeters.
        positions.push_back(x);
        positions.push_back(y);
        positions.push_back(z);
        colors.push_back({r / 255.0f, g / 255.0f, b / 255.0f});
    }

    if (positions.empty()) {
        std::cerr << "No points found in " << path << '\n';
        return 1;
    }
    if (idx_r < 0 && idx_rgb < 0 && idx_rgba < 0) {
        // The sample has only xyz. Map its Z range from blue to red.
        float minimum = positions[2], maximum = positions[2];
        for (size_t i = 2; i < positions.size(); i += 3) {
            minimum = std::min(minimum, positions[i]);
            maximum = std::max(maximum, positions[i]);
        }
        const float span = maximum > minimum ? maximum - minimum : 1;
        for (size_t i = 0; i < colors.size(); ++i) {
            const float t = (positions[3 * i + 2] - minimum) / span;
            colors[i] = {t, 0, 1 - t};
        }
    }
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    auto handle = viz->addPoints(positions, colors, 2.0f);
    viz->addAxes(0.5f);
    viz->setCameraPose({2.0f, -2.0f, 1.5f}, {0.0f, 0.0f, 0.0f},
                       {0.0f, 0.0f, 1.0f});
    viz->addText2D("PCD loaded (ASCII). Press Enter to exit.", 12, 12, 14,
                   {1, 1, 1});

    std::cout << "Loaded points: " << positions.size() / 3
              << " handle=" << handle << std::endl;
    if (!interrupt.waitForEnter(*viz)) return 130;

    viz->close();
    return 0;
}
