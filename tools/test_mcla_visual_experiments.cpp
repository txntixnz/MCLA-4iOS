#include "../MCLAApp/runtime/MCLAVisualExperiments.h"
#include "../MCLAApp/runtime/MCLAMetalPresentation.h"
#include <cassert>
#include <limits>
#include <cstdio>
#include <bit>
using namespace mcla::metal;
static std::array<uint8_t,16> GuestPosition(HudClip p) {
    std::array<uint8_t,16> bytes{};
    for(unsigned i=0;i<4;++i) {
        uint32_t word=std::bit_cast<uint32_t>(p[i]);
        for(unsigned j=0;j<4;++j) bytes[i*4+j]=uint8_t(word>>(24-j*8));
    }
    return bytes;
}
int main() {
    const HudMatrix matrix{{{2,0,0,0},{0,3,0,0},{0,0,4,0},{-1,1,2,1}}};
    const auto bytes=GuestPosition({2,3,4,99});
    for(uint32_t type:{0x2C23A5u,0x2A23B9u,0x1A23A6u}) {
        auto p=ProjectHudPosition(bytes,type,matrix);
        assert(p && (*p)[0]==3 && (*p)[1]==10 && (*p)[3]==1);
        assert((*p)[2]==(type==0x2C23A5 ? 2 : 18));
        assert(!ProjectHudPosition(std::span(bytes).first(HudPositionBytes(type)-1),type,matrix));
    }
    assert(!ProjectHudPosition(bytes,0x182886,matrix));
    assert(!ProjectHudPosition(GuestPosition({NAN,3,4,1}),0x1A23A6,matrix));
    auto invalidMatrix=matrix;invalidMatrix[3][3]=0;
    assert(!ProjectHudPosition(bytes,0x2A23B9,invalidMatrix));
    invalidMatrix=matrix;invalidMatrix[3][1]=INFINITY;
    assert(!ProjectHudPosition(bytes,0x2A23B9,invalidMatrix));
    // Authored screen coordinates replay through the actual decoder/transform.
    const HudMatrix screen{{{2.f/1280,0,0,0},{0,-2.f/720,0,0},{0,0,1,0},{-1,1,0,1}}};
    const std::array<HudClip,4> pixels{{{0,0,0,1},{1280,0,0,1},{1280,720,0,1},{0,720,0,1}}};
    for(uint32_t type:{0x2C23A5u,0x2A23B9u,0x1A23A6u}) {
        std::array<HudClip,4> clips{};
        for(unsigned i=0;i<4;++i) clips[i]=*ProjectHudPosition(GuestPosition(pixels[i]),type,screen);
        assert(FullScreenOverlay(clips,13));
        assert(FullScreenOverlay(std::span(clips).first(3),8));
    }
    const std::array<HudClip,4> quad{{{-1,-1,0,1},{1,-1,0,1},{1,1,0,1},{-1,1,0,1}}};
    const std::array<HudClip,4> strip{quad[0],quad[1],quad[3],quad[2]};
    const std::array<HudClip,6> triangles{quad[0],quad[1],quad[2],quad[0],quad[2],quad[3]};
    assert(FullScreenOverlay(quad,13));
    assert(FullScreenOverlay(quad,5));
    assert(FullScreenOverlay(strip,6));
    assert(FullScreenOverlay(triangles,4));
    assert(FullScreenOverlay(std::span(quad).first(3),8));
    assert(!FullScreenOverlay(std::span(quad).first(3),4)); // half-screen triangle has a full-screen AABB
    assert(!FullScreenOverlay(strip,13)); // crossed quad would expose a quarter of the scene
    assert(!FullScreenOverlay(quad,6));
    assert(!FullScreenOverlay(quad,2));
    auto duplicate=triangles;duplicate[5]=quad[1];
    assert(!FullScreenOverlay(duplicate,4)); // two copies of the same half-screen triangle
    auto separated=triangles;separated[3][0]+=.1f;separated[4][0]+=.1f;
    assert(!FullScreenOverlay(separated,4));
    auto hud=quad;
    for(auto& p:hud) {p[0]*=.3f;p[1]*=.2f;}
    assert(!FullScreenOverlay(hud,13));
    auto overscan=quad;
    for(auto& p:overscan) {p[0]*=1.2f;p[1]*=1.2f;}
    assert(FullScreenOverlay(overscan,13));
    const std::array<HudClip,3> largeTriangle{{{-1,-1,0,1},{3,-1,0,1},{-1,3,0,1}}};
    assert(FullScreenOverlay(largeTriangle,4));
    auto homogeneous=quad;
    for(auto& p:homogeneous) {p[0]*=2;p[1]*=2;p[3]=2;}
    assert(FullScreenOverlay(homogeneous,13));
    auto bad=quad;bad[0][3]=0;assert(!FullScreenOverlay(bad,13));
    bad=quad;bad[0][0]=NAN;assert(!FullScreenOverlay(bad,13));
    bad=quad;bad[0][3]=-1;assert(!FullScreenOverlay(bad,13));
    bad=quad;bad[0][3]=2;assert(!FullScreenOverlay(std::span(bad).first(3),8));
    auto inset=quad;
    for(auto& p:inset) {p[0]*=1-.5f/640;p[1]*=1-.5f/360;}
    assert(FullScreenOverlay(inset,13)); // half-pixel convention
    for(auto& p:inset) {p[0]*=.99f;p[1]*=.99f;}
    assert(!FullScreenOverlay(inset,13)); // visible border is not a full-screen fade
    // A fade and a loading tile share one batch. Only the fade may widen.
    for(uint32_t primitive:{4u,8u,13u}) {
        std::vector<HudClip> mixed;
        if(primitive==4) mixed.insert(mixed.end(),triangles.begin(),triangles.end());
        else mixed.insert(mixed.end(),quad.begin(),quad.begin()+(primitive==8 ? 3 : 4));
        const unsigned fadeCount=unsigned(mixed.size());
        mixed.insert(mixed.end(),hud.begin(),hud.begin()+(primitive==13 ? 4 : 3));
        auto ranges=HudOverlayRanges(mixed,primitive);
        assert(ranges.size()==2 && ranges[0].fullScreen && !ranges[1].fullScreen);
        assert(ranges[0].first==0 && ranges[0].count==fadeCount);
        assert(ranges[1].first==fadeCount && ranges[1].count==mixed.size()-fadeCount);
        unsigned next=0,expanded=0;
        for(const auto& r:ranges) {
            assert(r.first==next);next+=r.count;
            auto index=HudExpandedIndexRange(primitive,r.first,r.count);
            assert(index[0]==expanded);expanded+=index[1];
        }
        assert(next==mixed.size() && expanded==(primitive==4 ? 9 : 12));
    }
    std::vector<HudClip> maximum;
    maximum.insert(maximum.end(),quad.begin(),quad.end());
    for(unsigned i=1;i<1024;++i) maximum.insert(maximum.end(),hud.begin(),hud.end());
    auto ranges=HudOverlayRanges(maximum,13);
    assert(ranges.size()==1024 && ranges.front().fullScreen);
    unsigned full=0,next=0;
    for(const auto& r:ranges) {full+=r.fullScreen;assert(r.first==next);next+=r.count;}
    assert(full==1 && next==4096);
    maximum.push_back(quad[0]);assert(HudOverlayRanges(maximum,13).empty());
    // Phone scene remains native width; only qualified backgrounds use it.
    const auto phone=SceneExtent(1280,720,720,1560,720);
    const auto frame=HudSafeFrame(phone.width,phone.height);
    assert(phone.width==1560 && phone.height==720 && frame.left==140 && frame.width==1280);
    const uint32_t fullScissor=(720u<<16)|1280;
    assert(HudOverlayViewport(0,0,1280,720,0,fullScissor));
    assert(!HudOverlayViewport(0,0,640,720,0,fullScissor));
    assert(!HudOverlayViewport(0,0,1280,720,100,fullScissor));
    assert(!HudOverlayViewport(0,0,1280,720,0,(720u<<16)|1000));
    assert(!HudOverlayViewport(NAN,0,1280,720,0,fullScissor));
    assert(HudExpandedIndexRange(13,4,8)==(std::array<uint32_t,2>{6,12}));
    assert(HudExpandedIndexRange(8,3,6)==(std::array<uint32_t,2>{6,12}));
    puts("HUD overlays passed: Float2/3/4 guest inputs, topology coverage, overscan, mixed batches, index spans and native phone extent");
}
