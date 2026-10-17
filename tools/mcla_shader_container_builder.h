#pragma once
#include <algorithm>
#include <cstdint>
#include <string_view>
#include <vector>
namespace mcla::shader {
constexpr uint32_t kShaderContainerMagic=0x102A1100u;
inline void AppendBe32(std::vector<uint8_t>& bytes, uint32_t value) {
    bytes.push_back(static_cast<uint8_t>(value >> 24));
    bytes.push_back(static_cast<uint8_t>(value >> 16));
    bytes.push_back(static_cast<uint8_t>(value >> 8));
    bytes.push_back(static_cast<uint8_t>(value));
}

inline void AppendBe16(std::vector<uint8_t>& bytes, uint16_t value) {
    bytes.push_back(static_cast<uint8_t>(value >> 8));
    bytes.push_back(static_cast<uint8_t>(value));
}

inline void StoreBe32(std::vector<uint8_t>& bytes, size_t offset, uint32_t value) {
    bytes.at(offset + 0) = static_cast<uint8_t>(value >> 24);
    bytes.at(offset + 1) = static_cast<uint8_t>(value >> 16);
    bytes.at(offset + 2) = static_cast<uint8_t>(value >> 8);
    bytes.at(offset + 3) = static_cast<uint8_t>(value);
}

inline uint32_t LoadLe32(const uint8_t* bytes) {
    return uint32_t(bytes[0]) | uint32_t(bytes[1]) << 8 |
           uint32_t(bytes[2]) << 16 | uint32_t(bytes[3]) << 24;
}

inline uint32_t LoadBe32(const uint8_t* bytes) {
    return uint32_t(bytes[0]) << 24 | uint32_t(bytes[1]) << 16 |
           uint32_t(bytes[2]) << 8 | uint32_t(bytes[3]);
}

inline void StoreBe32Raw(uint8_t* bytes, uint32_t value) {
    bytes[0] = static_cast<uint8_t>(value >> 24);
    bytes[1] = static_cast<uint8_t>(value >> 16);
    bytes[2] = static_cast<uint8_t>(value >> 8);
    bytes[3] = static_cast<uint8_t>(value);
}

inline size_t AlignUp(size_t value, size_t alignment) {
    return (value + alignment - 1) & ~(alignment - 1);
}

inline uint32_t PatchNoOpVertexFetches(std::vector<uint8_t>& microcode) {
    // XenosRecomp currently prints an invalid empty swizzle for a vfetch whose
    // four destination components are all KEEP. Such an instruction has no
    // architectural write. Mark it as an unsupported fetch opcode in the
    // synthetic compiler input so the compiler emits no operation, preserving
    // the guest behavior without touching the captured source microcode.
    const size_t dwordCount = microcode.size() / 4;
    size_t controlFlowLimit = dwordCount;
    struct ExecRef {
        uint32_t address;
        uint32_t count;
        uint32_t sequence;
    };
    std::vector<ExecRef> execs;
    for (size_t i = 0; i + 2 < controlFlowLimit; i += 3) {
        const uint32_t d0 = LoadBe32(microcode.data() + i * 4);
        const uint32_t d1 = LoadBe32(microcode.data() + (i + 1) * 4);
        const uint32_t d2 = LoadBe32(microcode.data() + (i + 2) * 4);
        const uint32_t word0[2] = {d0, (d1 >> 16) | (d2 << 16)};
        const uint32_t word1[2] = {d1 & 0xFFFFu, d2 >> 16};
        for (size_t half = 0; half < 2; ++half) {
            const uint32_t opcode = (word1[half] >> 12) & 0xFu;
            if (!((opcode >= 1 && opcode <= 6) || opcode == 13 ||
                  opcode == 14)) {
                continue;
            }
            const uint32_t address = word0[half] & 0xFFFu;
            if (address && static_cast<size_t>(address) * 3 < controlFlowLimit) {
                controlFlowLimit = static_cast<size_t>(address) * 3;
            }
            execs.push_back({address, (word0[half] >> 12) & 7u,
                             (word0[half] >> 16) & 0xFFFu});
        }
    }

    uint32_t patched = 0;
    for (const ExecRef& exec : execs) {
        for (uint32_t i = 0; i < std::min(exec.count, 6u); ++i) {
            if (((exec.sequence >> (i * 2)) & 1u) == 0) {
                continue;
            }
            const size_t base = static_cast<size_t>(exec.address + i) * 3;
            if (base + 2 >= dwordCount) {
                continue;
            }
            uint32_t word0 = LoadBe32(microcode.data() + base * 4);
            const uint32_t word1 =
                LoadBe32(microcode.data() + (base + 1) * 4);
            if ((word0 & 0x1Fu) == 0 && (word1 & 0xFFFu) == 0xFFFu) {
                word0 = (word0 & ~0x1Fu) | 31u;
                StoreBe32Raw(microcode.data() + base * 4, word0);
                ++patched;
            }
        }
    }
    return patched;
}

inline void AppendSyntheticConstantTable(std::vector<uint8_t>& bytes,
                                  uint16_t registerCount) {
    // XenosRecomp names float constants through the source D3DX constant
    // table. Runtime-captured microcode no longer carries that source table,
    // so expose the complete stage constant bank as one array. This preserves
    // direct and relative cN addressing without inventing title symbols.
    constexpr std::string_view kName = "g_MCLAConstants";
    constexpr uint32_t kConstantTableBytes = 7 * sizeof(uint32_t);
    constexpr uint32_t kConstantInfoBytes = 20;
    constexpr uint32_t kNameOffset =
        kConstantTableBytes + kConstantInfoBytes;
    AppendBe32(bytes, kNameOffset + static_cast<uint32_t>(kName.size()) + 1);
    AppendBe32(bytes, 0x1Cu);
    AppendBe32(bytes, 0u);      // creator
    AppendBe32(bytes, 0u);      // version
    AppendBe32(bytes, 1u);      // constants
    AppendBe32(bytes, 0x1Cu);   // constantInfo
    AppendBe32(bytes, 0u);      // flags
    AppendBe32(bytes, 0u);      // target

    AppendBe32(bytes, kNameOffset);
    AppendBe16(bytes, 2u);      // D3DXRS_FLOAT4
    AppendBe16(bytes, 0u);      // register index
    AppendBe16(bytes, registerCount);
    AppendBe16(bytes, 0u);      // reserved
    AppendBe32(bytes, 0u);      // typeInfo (not consulted by XenosRecomp)
    AppendBe32(bytes, 0u);      // defaultValue
    bytes.insert(bytes.end(), kName.begin(), kName.end());
    bytes.push_back(0);
}

inline void AppendProvisionalIntegerDefinitions(std::vector<uint8_t>& bytes) {
    // DefinitionTable header. Runtime shader objects expose the executable
    // microcode and descriptor ABI, but not the original FXC definition
    // table. Declare every loop register so the recovered program is
    // compilable. A value of one preserves a single loop iteration and keeps
    // this corpus useful for pipeline bring-up; these provisional values are
    // explicitly not a substitute for capturing the title's real integer
    // constants before native takeover.
    for (uint32_t i = 0; i < 4; ++i) {
        AppendBe32(bytes, 0u);
    }
    AppendBe32(bytes, 0u);  // size (not consumed by XenosRecomp)
    AppendBe32(bytes, 0u);  // no float definitions

    AppendBe16(bytes, 8992u);  // integer register file base
    AppendBe16(bytes, 32u);
    AppendBe32(bytes, 0u);     // second definition-header dword
    for (uint32_t i = 0; i < 32; ++i) {
        AppendBe32(bytes, 0x01010101u);
    }
    AppendBe32(bytes, 0u);  // integer-definition terminator
}

inline std::vector<uint8_t> BuildContainer(bool pixel,
                                    const std::vector<uint8_t>& microcode,
                                    const std::vector<uint32_t>& elements,
                                    const std::vector<uint32_t>& interpolators,
                                    uint32_t pixelOutputs) {
    constexpr size_t kHeaderBytes = 9 * sizeof(uint32_t);
    constexpr size_t kConstantTableOffset = kHeaderBytes;

    std::vector<uint8_t> bytes(kHeaderBytes, 0);
    // The ALU encoding exposes an eight-bit constant address in both stages.
    // MCLA flushes all 256 registers in BOTH banks. The build pipeline also
    // widens XenosRecomp's GTA-specific pixel-array guard to match this ABI.
    // Returning zero for c224..255 destroys post-processing (e.g. c255 is
    // the four-tap downsample multiplier).
    AppendSyntheticConstantTable(bytes, 256u);
    bytes.resize(AlignUp(bytes.size(), 4), 0);
    const size_t definitionTableOffset = bytes.size();
    AppendProvisionalIntegerDefinitions(bytes);
    const size_t shaderOffset = AlignUp(bytes.size(), 16);
    bytes.resize(shaderOffset, 0);

    AppendBe32(bytes, 0u);  // physicalOffset: microcode starts at physical base
    AppendBe32(bytes, static_cast<uint32_t>(microcode.size()));
    AppendBe32(bytes, 0u);  // field8
    AppendBe32(bytes, 0u);  // fieldC / SV_Position register
    AppendBe32(bytes, 0u);  // field10
    AppendBe32(bytes, static_cast<uint32_t>(interpolators.size()) << 5);
    AppendBe32(bytes, 0u);  // field18
    if (pixel) {
        AppendBe32(bytes, pixelOutputs);
        for (uint32_t value : interpolators) {
            AppendBe32(bytes, value);
        }
    } else {
        AppendBe32(bytes, static_cast<uint32_t>(elements.size()));
        AppendBe32(bytes, 0u);  // field20
        for (uint32_t value : elements) {
            AppendBe32(bytes, value);
        }
        for (uint32_t value : interpolators) {
            AppendBe32(bytes, value);
        }
    }

    const size_t virtualSize = AlignUp(bytes.size(), 16);
    bytes.resize(virtualSize, 0);
    std::vector<uint8_t> compilerMicrocode = microcode;
    if (!pixel) {
        PatchNoOpVertexFetches(compilerMicrocode);
    }
    bytes.insert(bytes.end(), compilerMicrocode.begin(),
                 compilerMicrocode.end());

    StoreBe32(bytes, 0, kShaderContainerMagic | (pixel ? 0u : 1u));
    StoreBe32(bytes, 4, static_cast<uint32_t>(virtualSize));
    StoreBe32(bytes, 8, static_cast<uint32_t>(microcode.size()));
    StoreBe32(bytes, 12, static_cast<uint32_t>(kHeaderBytes));
    StoreBe32(bytes, 16, static_cast<uint32_t>(kConstantTableOffset));
    StoreBe32(bytes, 20, static_cast<uint32_t>(definitionTableOffset));
    StoreBe32(bytes, 24, static_cast<uint32_t>(shaderOffset));
    StoreBe32(bytes, 28, 0u);
    StoreBe32(bytes, 32, 0u);
    return bytes;
}

}
