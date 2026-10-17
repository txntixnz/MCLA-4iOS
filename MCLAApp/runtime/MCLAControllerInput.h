#pragma once
#include <cstdint>

namespace mcla::input {
struct PadSample {
    uint16_t buttons=0;
    uint8_t leftTrigger=0,rightTrigger=0;
    int16_t leftX=0,leftY=0,rightX=0,rightY=0;
    bool operator==(const PadSample&) const = default;
};
// The platform driver updates its packet for digital edges only. Track the
// complete sampled pad before touch merging, including analog-only changes.
class ControllerPacket {
    PadSample previous_{};
    uint32_t packet_=0;
    bool sampled_=false;
public:
    uint32_t Observe(const PadSample& sample) {
        if(!sampled_ || !(sample==previous_)) {
            previous_=sample; sampled_=true; ++packet_;
        }
        return packet_;
    }
};
constexpr bool TouchControlsActive(bool gameVisible,bool foreground,bool enabled,bool controller) {
    return gameVisible && foreground && enabled && !controller;
}
}
