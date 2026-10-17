#pragma once
#include <algorithm>
#include <array>
#include <optional>
#include <string_view>

namespace mcla::touch {
enum class XboxAnchor { Left,Center,Right };
struct XboxControl {
    std::string_view key;
    XboxAnchor anchor;
    double x,y,width,height;
};
// Authored Xbox arrangement. The side groups anchor to the physical edges;
// their spacing and circular artwork share one scale, even on wide phones.
inline constexpr std::array<XboxControl,19> xboxControls{{
    {"steer",XboxAnchor::Left,150,420,190,190},
    {"look",XboxAnchor::Right,935,590,190,190},
    {"brake",XboxAnchor::Left,130,230,148,76},
    {"ability",XboxAnchor::Left,315,230,148,76},
    {"gas",XboxAnchor::Right,1150,230,148,76},
    {"camera",XboxAnchor::Right,965,230,148,76},
    {"headlights",XboxAnchor::Right,1120,328,100,100},
    {"nitro",XboxAnchor::Right,1018,430,100,100},
    {"weight",XboxAnchor::Right,1222,430,100,100},
    {"handbrake",XboxAnchor::Right,1120,532,100,100},
    {"hud",XboxAnchor::Left,340,480,86,86},
    {"track_left",XboxAnchor::Left,250,570,86,86},
    {"track_right",XboxAnchor::Left,430,570,86,86},
    {"hydraulics",XboxAnchor::Left,340,660,86,86},
    {"gps",XboxAnchor::Center,595,660,70,70},
    {"pause",XboxAnchor::Center,685,660,70,70},
    {"info",XboxAnchor::Left,180,650,72,72},
    {"horn",XboxAnchor::Right,795,610,72,72},
    {"guide",XboxAnchor::Center,640,300,70,70},
}};
struct XboxFrame { double x,y,width,height; };
inline std::optional<XboxFrame> XboxControlFrame(std::string_view key,double width,double height) {
    if(!(width>0) || !(height>0)) return std::nullopt;
    for(const auto& c:xboxControls) if(c.key==key) {
        const double scale=std::min(width/1280.,height/720.);
        const double x=c.anchor==XboxAnchor::Left ? c.x*scale :
            c.anchor==XboxAnchor::Right ? width-(1280-c.x)*scale : width*.5+(c.x-640)*scale;
        const double y=height-(720-c.y)*scale;
        return XboxFrame{x,y,c.width*scale,c.height*scale};
    }
    return std::nullopt;
}
}
