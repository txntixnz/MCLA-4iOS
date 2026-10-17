#pragma once
#include <cstdint>
#include <algorithm>
#include <cmath>

namespace mcla::input {
// Normal GameController input is already 0..1. Only an explicit calibration
// changes these endpoints; learning a peak during driving would turn a gentle
// first squeeze into full throttle.
struct TriggerRange {
    float released=0, full=1;
    bool Valid() const {
        return std::isfinite(released) && std::isfinite(full) && released>=0 &&
            full<=1 && full-released>=.05f;
    }
    uint8_t Convert(float raw) const {
        if(!std::isfinite(raw)) return 0;
        const auto range=Valid() ? *this : TriggerRange{};
        return static_cast<uint8_t>(std::lround(
            std::clamp((raw-range.released)/(range.full-range.released),0.f,1.f)*255.f));
    }
};
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
