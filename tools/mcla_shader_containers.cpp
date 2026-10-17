#include "mcla_shader_container_builder.h"
#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace fs = std::filesystem;

namespace {

using namespace mcla::shader;

struct ShaderMetadata {
    uint32_t vertexElements = 0;
    uint32_t vertexInterpolators = 0;
    uint32_t pixelInterpolators = 0;
    uint32_t pixelOutputs = 0;
    bool hasVertex = false;
    bool hasPixel = false;
};

bool ReadFile(const fs::path& path, std::vector<uint8_t>& bytes) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input) {
        return false;
    }
    const std::streamsize size = input.tellg();
    if (size < 0) {
        return false;
    }
    input.seekg(0);
    bytes.resize(static_cast<size_t>(size));
    return size == 0 ||
           bool(input.read(reinterpret_cast<char*>(bytes.data()), size));
}

bool WriteFile(const fs::path& path, const std::vector<uint8_t>& bytes) {
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    if (error) {
        return false;
    }
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) {
        return false;
    }
    output.write(reinterpret_cast<const char*>(bytes.data()),
                 static_cast<std::streamsize>(bytes.size()));
    return output.good();
}

std::optional<std::string> JsonString(std::string_view line,
                                      std::string_view key) {
    const std::string needle = "\"" + std::string(key) + "\":\"";
    const size_t start = line.find(needle);
    if (start == std::string_view::npos) {
        return std::nullopt;
    }
    const size_t value = start + needle.size();
    const size_t end = line.find('"', value);
    if (end == std::string_view::npos) {
        return std::nullopt;
    }
    return std::string(line.substr(value, end - value));
}

std::optional<uint32_t> JsonUint(std::string_view line,
                                 std::string_view key) {
    const std::string needle = "\"" + std::string(key) + "\":";
    const size_t start = line.find(needle);
    if (start == std::string_view::npos) {
        return std::nullopt;
    }
    size_t cursor = start + needle.size();
    uint64_t value = 0;
    bool found = false;
    while (cursor < line.size() && line[cursor] >= '0' &&
           line[cursor] <= '9') {
        found = true;
        value = value * 10 + uint32_t(line[cursor] - '0');
        if (value > UINT32_MAX) {
            return std::nullopt;
        }
        ++cursor;
    }
    return found ? std::optional<uint32_t>(static_cast<uint32_t>(value))
                 : std::nullopt;
}

bool MergeMetadata(std::map<std::string, ShaderMetadata>& metadata,
                   std::string_view line, std::string& error) {
    const auto vs = JsonString(line, "vs");
    const auto ps = JsonString(line, "ps");
    if (!vs || !ps) {
        return true;
    }

    if (const auto elements = JsonUint(line, "vs_elements")) {
        const auto interpolators = JsonUint(line, "vs_interpolators");
        if (!interpolators) {
            error = "manifest record has incomplete vertex metadata";
            return false;
        }
        auto& entry = metadata[*vs];
        if (entry.hasVertex &&
            (entry.vertexElements != *elements ||
             entry.vertexInterpolators != *interpolators)) {
            error = "conflicting vertex metadata for " + *vs;
            return false;
        }
        entry.vertexElements = *elements;
        entry.vertexInterpolators = *interpolators;
        entry.hasVertex = true;
    }

    if (const auto interpolators = JsonUint(line, "ps_interpolators")) {
        const auto outputs = JsonUint(line, "ps_outputs");
        if (!outputs) {
            error = "manifest record has incomplete pixel metadata";
            return false;
        }
        auto& entry = metadata[*ps];
        if (entry.hasPixel &&
            (entry.pixelInterpolators != *interpolators ||
             entry.pixelOutputs != *outputs)) {
            error = "conflicting pixel metadata for " + *ps;
            return false;
        }
        entry.pixelInterpolators = *interpolators;
        entry.pixelOutputs = *outputs;
        entry.hasPixel = true;
    }
    return true;
}

bool ReadPackedDwords(const fs::path& path, uint32_t expectedCount,
                      std::vector<uint32_t>& values, std::string& error) {
    values.clear();
    if (expectedCount == 0) {
        return true;
    }
    std::vector<uint8_t> bytes;
    if (!ReadFile(path, bytes)) {
        error = "missing metadata file: " + path.string();
        return false;
    }
    if (bytes.size() != static_cast<size_t>(expectedCount) * 4) {
        error = "metadata size mismatch: " + path.string();
        return false;
    }
    values.reserve(expectedCount);
    for (uint32_t i = 0; i < expectedCount; ++i) {
        values.push_back(LoadLe32(bytes.data() + static_cast<size_t>(i) * 4));
    }
    return true;
}

std::string IdentityFromShaderFilename(const fs::path& path, bool& pixel) {
    const std::string stem = path.stem().string();
    if (stem.size() != 19 || stem[2] != '-' ||
        (stem.rfind("vs-", 0) != 0 && stem.rfind("ps-", 0) != 0)) {
        return {};
    }
    pixel = stem[0] == 'p';
    const std::string identity = stem.substr(3);
    if (!std::all_of(identity.begin(), identity.end(), [](char c) {
            return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F');
        })) {
        return {};
    }
    return identity;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: mcla_shader_containers <native-capture-dir> "
                     "<output-dir>\n";
        return 2;
    }
    const fs::path captureRoot = argv[1];
    const fs::path outputRoot = argv[2];

    std::ifstream manifest(captureRoot / "manifest.jsonl");
    if (!manifest) {
        std::cerr << "cannot read capture manifest\n";
        return 1;
    }
    std::map<std::string, ShaderMetadata> metadata;
    std::string line;
    std::string error;
    while (std::getline(manifest, line)) {
        if (!MergeMetadata(metadata, line, error)) {
            std::cerr << error << '\n';
            return 1;
        }
    }

    std::error_code fsError;
    fs::create_directories(outputRoot, fsError);
    if (fsError) {
        std::cerr << "cannot create output directory: " << fsError.message()
                  << '\n';
        return 1;
    }
    std::ofstream mapFile(outputRoot / "identities.tsv",
                          std::ios::binary | std::ios::trunc);
    mapFile << "stage\tidentity\tcontainer\tmicrocode_bytes\telements\tinterpolators\toutputs\n";

    uint32_t vertexWritten = 0;
    uint32_t pixelWritten = 0;
    uint32_t skippedNoMetadata = 0;
    uint32_t failed = 0;
    for (const auto& entry : fs::directory_iterator(captureRoot / "shaders")) {
        if (!entry.is_regular_file() || entry.path().extension() != ".bin") {
            continue;
        }
        bool pixel = false;
        const std::string identity =
            IdentityFromShaderFilename(entry.path(), pixel);
        if (identity.empty()) {
            continue;
        }
        const auto metadataIt = metadata.find(identity);
        if (metadataIt == metadata.end() ||
            (pixel ? !metadataIt->second.hasPixel
                   : !metadataIt->second.hasVertex)) {
            ++skippedNoMetadata;
            continue;
        }

        const ShaderMetadata& shaderMetadata = metadataIt->second;
        std::vector<uint8_t> microcode;
        if (!ReadFile(entry.path(), microcode) || microcode.empty() ||
            microcode.size() % 12 != 0 || microcode.size() > UINT32_MAX) {
            std::cerr << "invalid microcode: " << entry.path() << '\n';
            ++failed;
            continue;
        }

        std::vector<uint32_t> elements;
        std::vector<uint32_t> interpolators;
        const fs::path metadataRoot = captureRoot / "metadata";
        if (!pixel) {
            if (!ReadPackedDwords(metadataRoot /
                                      ("vs-elements-" + identity + ".bin"),
                                  shaderMetadata.vertexElements, elements,
                                  error) ||
                !ReadPackedDwords(metadataRoot /
                                      ("vs-interpolators-" + identity + ".bin"),
                                  shaderMetadata.vertexInterpolators,
                                  interpolators, error)) {
                std::cerr << error << '\n';
                ++failed;
                continue;
            }
        } else if (!ReadPackedDwords(
                       metadataRoot /
                           ("ps-interpolators-" + identity + ".bin"),
                       shaderMetadata.pixelInterpolators, interpolators,
                       error)) {
            std::cerr << error << '\n';
            ++failed;
            continue;
        }

        const std::vector<uint8_t> container = BuildContainer(
            pixel, microcode, elements, interpolators,
            shaderMetadata.pixelOutputs);
        const std::string filename =
            std::string(pixel ? "ps-" : "vs-") + identity + ".bin";
        if (!WriteFile(outputRoot / filename, container)) {
            std::cerr << "cannot write " << filename << '\n';
            ++failed;
            continue;
        }
        mapFile << (pixel ? "pixel" : "vertex") << '\t' << identity << '\t'
                << filename << '\t' << microcode.size() << '\t'
                << elements.size() << '\t' << interpolators.size() << '\t'
                << (pixel ? shaderMetadata.pixelOutputs : 0) << '\n';
        pixel ? ++pixelWritten : ++vertexWritten;
    }

    std::ofstream summary(outputRoot / "summary.txt",
                          std::ios::binary | std::ios::trunc);
    summary << "vertex_containers=" << vertexWritten << '\n'
            << "pixel_containers=" << pixelWritten << '\n'
            << "skipped_without_authoritative_metadata=" << skippedNoMetadata
            << '\n'
            << "failed=" << failed << '\n';
    std::cout << "MCLA shader containers: " << vertexWritten << " vertex, "
              << pixelWritten << " pixel, " << skippedNoMetadata
              << " skipped without authoritative metadata, " << failed
              << " failed\n";
    return failed == 0 ? 0 : 1;
}
