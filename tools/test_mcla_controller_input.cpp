#include "../MCLAApp/runtime/MCLAControllerInput.h"
#include "../MCLAApp/ios/MCLAXboxTouchLayout.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>
int main() {
    using namespace mcla::input;
    ControllerPacket packet;
    PadSample pad{};
    auto current=packet.Observe(pad);
    assert(current==1 && packet.Observe(pad)==current);
    pad.buttons=0x1000;
    assert(packet.Observe(pad)==++current);
    // Digital state stays held while analog-only changes continue to arrive.
    for(int value:{1,128,255,0}) {
        pad.rightTrigger=value;assert(packet.Observe(pad)==++current);
        pad.leftTrigger=value;assert(packet.Observe(pad)==++current);
        assert(packet.Observe(pad)==current);
    }
    for(int value:{-32768,-100,32767,0}) {
        pad.leftX=value;assert(packet.Observe(pad)==++current);
        pad.leftY=value;assert(packet.Observe(pad)==++current);
        pad.rightX=value;assert(packet.Observe(pad)==++current);
        pad.rightY=value;assert(packet.Observe(pad)==++current);
        assert(packet.Observe(pad)==current);
    }
    pad={};assert(packet.Observe(pad)==++current); // disconnect/background release
    assert(packet.Observe(pad)==current);
    pad.buttons=0x8000;assert(packet.Observe(pad)==++current); // reconnect
    for(int flags=0;flags<16;++flags)
        assert(TouchControlsActive(flags&1,flags&2,flags&4,flags&8)==(flags==7));
    using namespace mcla::touch;
    for(const auto& size:{std::array{834.,407.},std::array{926.,428.},
                          std::array{1024.,768.},std::array{1366.,1024.},std::array{1280.,720.}}) {
        std::vector<XboxFrame> frames;
        for(const auto& c:xboxControls) {
            auto f=XboxControlFrame(c.key,size[0],size[1]);assert(f);
            assert(f->x-f->width/2>=0 && f->x+f->width/2<=size[0]);
            assert(f->y-f->height/2>=0 && f->y+f->height/2<=size[1]);
            for(const auto& p:frames) {
                bool separate=std::fabs(f->x-p.x)>=(f->width+p.width)/2 ||
                    std::fabs(f->y-p.y)>=(f->height+p.height)/2;
                if(!separate) std::fprintf(stderr,"Overlap: %s / %s at %.0fx%.0f\n",c.key.data(),xboxControls[&p-frames.data()].key.data(),size[0],size[1]);
                assert(separate);
            }
            frames.push_back(*f);
        }
        auto a=*XboxControlFrame("handbrake",size[0],size[1]);
        auto b=*XboxControlFrame("weight",size[0],size[1]);
        auto x=*XboxControlFrame("nitro",size[0],size[1]);
        auto y=*XboxControlFrame("headlights",size[0],size[1]);
        assert(a.y>b.y && b.x>a.x && x.x<a.x && y.y<b.y);
        assert(std::fabs(a.x-y.x)<.001 && std::fabs(b.y-x.y)<.001);
        assert(XboxControlFrame("steer",size[0],size[1])->x<size[0]*.5);
        assert(XboxControlFrame("look",size[0],size[1])->x>size[0]*.5);
        for(auto key:{"gps","pause"}) {
            auto menu=*XboxControlFrame(key,size[0],size[1]);
            assert(menu.y-menu.height/2>size[1]*.8);
        }
    }
    assert(!XboxControlFrame("missing",834,407));
    assert(!XboxControlFrame("steer",0,407));
    puts("PASS: controller analog/digital packets, release/reconnect, touch ownership and nonoverlapping Xbox layouts across phone/tablet extents");
}
