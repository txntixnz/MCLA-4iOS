#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <optional>
#include <span>
#include <vector>
namespace mcla::metal {
enum VisualExperiment : unsigned {
    PackedVertexColor = 1, FullScreenFades = 2, StableMaterialLOD = 4, RaisedDrivingHUD = 8
};
using HudClip = std::array<float,4>;
using HudMatrix = std::array<HudClip,4>;
constexpr unsigned HudPositionBytes(uint32_t type) {
    return type==0x2C23A5 ? 8 : type==0x2A23B9 ? 12 : type==0x1A23A6 ? 16 : 0;
}
// Match the audited F8B6972A1D56B354 input and ALU. Float2 fetches supply z=0;
// Float4's w is unused by this shader, which adds c11 without multiplying it.
inline std::optional<HudClip> ProjectHudPosition(std::span<const uint8_t> bytes,
                                                uint32_t type, const HudMatrix& matrix) {
    const unsigned size=HudPositionBytes(type);
    if (!size || bytes.size()<size) return std::nullopt;
    float xyz[3]{};
    for (unsigned i=0;i<std::min(3u,size/4);++i) {
        const auto* p=bytes.data()+i*4;
        uint32_t word=(uint32_t(p[0])<<24)|(uint32_t(p[1])<<16)|(uint32_t(p[2])<<8)|p[3];
        std::memcpy(&xyz[i],&word,4);
    }
    HudClip clip{};
    for (unsigned i=0;i<4;++i) {
        clip[i]=xyz[0]*matrix[0][i]+xyz[1]*matrix[1][i]+xyz[2]*matrix[2][i]+matrix[3][i];
        if (!std::isfinite(clip[i])) return std::nullopt;
    }
    if (clip[3]<=0) return std::nullopt;
    return clip;
}
namespace overlay_detail {
using Point=std::array<double,2>;
inline double Cross(Point a, Point b, Point c) {
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
}
inline bool Same(Point a,Point b) {
    return std::fabs(a[0]-b[0])<1e-6 && std::fabs(a[1]-b[1])<1e-6;
}
// Require a connected convex triangle/quad, not just a screen-sized AABB.
inline bool CoversScreen(std::span<const Point> triangles) {
    if (triangles.size()!=3 && triangles.size()!=6) return false;
    const double area0=std::fabs(Cross(triangles[0],triangles[1],triangles[2]));
    if (area0<1e-9) return false;
    double area=area0;
    if (triangles.size()==6) {
        unsigned shared=0;
        std::array<Point,2> edge{};
        Point outside0{},outside1{};
        for (unsigned i=0;i<3;++i)
            for (unsigned j=3;j<6;++j)
                if(Same(triangles[i],triangles[j])) {
                    if(shared<2) edge[shared]=triangles[i];
                    ++shared;
                }
        if (shared!=2) return false;
        for(unsigned i=0;i<3;++i)
            if(!Same(triangles[i],edge[0]) && !Same(triangles[i],edge[1])) outside0=triangles[i];
        for(unsigned i=3;i<6;++i)
            if(!Same(triangles[i],edge[0]) && !Same(triangles[i],edge[1])) outside1=triangles[i];
        if(Cross(edge[0],edge[1],outside0)*Cross(edge[0],edge[1],outside1)>=0) return false;
        const double area1=std::fabs(Cross(triangles[3],triangles[4],triangles[5]));
        if (area1<1e-9) return false;
        area+=area1;
    }
    std::array<Point,6> sorted{};
    std::copy(triangles.begin(),triangles.end(),sorted.begin());
    auto end=sorted.begin()+triangles.size();
    std::sort(sorted.begin(),end);
    end=std::unique(sorted.begin(),end,Same);
    const unsigned n=unsigned(end-sorted.begin());
    std::array<Point,12> hull{};
    unsigned k=0;
    for (unsigned i=0;i<n;++i) {
        while(k>=2 && Cross(hull[k-2],hull[k-1],sorted[i])<=0) --k;
        hull[k++]=sorted[i];
    }
    for (int i=int(n)-2, lower=int(k)+1;i>=0;--i) {
        while(int(k)>=lower && Cross(hull[k-2],hull[k-1],sorted[i])<=0) --k;
        hull[k++]=sorted[i];
    }
    if (k<4) return false;
    --k;
    double hullArea=0;
    for(unsigned i=1;i+1<k;++i) hullArea+=Cross(hull[0],hull[i],hull[i+1]);
    if (std::fabs(hullArea-area)>std::max(1e-8,area*1e-6)) return false;
    // Allow the title's half-pixel placement, at most one authored pixel.
    for (Point corner: {Point{-1+2./1280,-1+2./720},Point{1-2./1280,-1+2./720},
                        Point{1-2./1280,1-2./720},Point{-1+2./1280,1-2./720}})
        for(unsigned i=0;i<k;++i)
            if(Cross(hull[i],hull[(i+1)%k],corner)<-1e-9) return false;
    return true;
}
}
// Guest primitives: triangle list=4, fan=5, strip=6, rectangle list=8,
// quad list=13. Check actual triangle coverage, including overscan.
inline bool FullScreenOverlay(std::span<const HudClip> clips,uint32_t primitive) {
    if (clips.size()<3 || clips.size()>6) return false;
    std::array<overlay_detail::Point,6> p{};
    for(unsigned i=0;i<clips.size();++i) {
        const auto& c=clips[i];
        if(!std::isfinite(c[3]) || c[3]<=0) return false;
        p[i]={double(c[0])/c[3],double(c[1])/c[3]};
        if(!std::isfinite(p[i][0]) || !std::isfinite(p[i][1])) return false;
    }
    if(primitive!=8) {
        double left=INFINITY,top=INFINITY,right=-INFINITY,bottom=-INFINITY;
        for(unsigned i=0;i<clips.size();++i) {
            left=std::min(left,p[i][0]);right=std::max(right,p[i][0]);
            top=std::min(top,p[i][1]);bottom=std::max(bottom,p[i][1]);
        }
        if(left>-1+2./1280 || right<1-2./1280 ||
           top>-1+2./720 || bottom<1-2./720) return false;
    }
    if(primitive==4 && (clips.size()==3 || clips.size()==6))
        return overlay_detail::CoversScreen({p.data(),clips.size()});
    if((primitive==5 || primitive==6) && clips.size()==3)
        return overlay_detail::CoversScreen({p.data(),3});
    if(primitive==8 && clips.size()==3) {
        // HUD rectangles use an affine projection. Do not guess a missing
        // corner after perspective division when their homogeneous w differs.
        for(const auto& c:clips)
            if(std::fabs(double(c[3])-clips[0][3])>std::fabs(double(clips[0][3]))*1e-6) return false;
        // The renderer reconstructs the corner opposite the longest edge.
        unsigned first=0;
        double longest=-1;
        for(unsigned i=0;i<3;++i) {
            auto a=p[(i+1)%3],b=p[(i+2)%3];
            const double length=std::hypot(a[0]-b[0],a[1]-b[1]);
            if(length>longest) {longest=length;first=i;}
        }
        const auto a=p[first],b=p[(first+1)%3],c=p[(first+2)%3];
        std::array<overlay_detail::Point,6> t{a,b,c,c,b,
            overlay_detail::Point{b[0]-a[0]+c[0],b[1]-a[1]+c[1]}};
        return overlay_detail::CoversScreen(t);
    }
    if(clips.size()!=4) return false;
    std::array<overlay_detail::Point,6> t{};
    if(primitive==13 || primitive==5) t={p[0],p[1],p[2],p[0],p[2],p[3]};
    else if(primitive==6) t={p[0],p[1],p[2],p[2],p[1],p[3]};
    else return false;
    return overlay_detail::CoversScreen(t);
}
struct HudGeometryRange { uint32_t first,count; bool fullScreen; };
inline bool HudOverlayViewport(float x,float y,float width,float height,uint32_t tl,uint32_t br) {
    return std::fabs(x)<=1 && std::fabs(y)<=1 &&
        std::fabs(width-1280)<=1 && std::fabs(height-720)<=1 &&
        (tl&32767)<=1 && ((tl>>16)&32767)<=1 &&
        (br&32767)>=1279 && ((br>>16)&32767)>=719;
}
// Split only independent primitives, preserving order and complete quad pairs.
inline std::vector<HudGeometryRange> HudOverlayRanges(std::span<const HudClip> clips,
                                                      uint32_t primitive) {
    std::vector<HudGeometryRange> ranges;
    if(clips.size()<3 || clips.size()>4096) return ranges;
    const unsigned step=primitive==13 ? 4 : (primitive==4 || primitive==8) ? 3 : 0;
    ranges.reserve(step ? clips.size()/step : 1);
    if(!step || clips.size()%step) {
        ranges.push_back({0,uint32_t(clips.size()),FullScreenOverlay(clips,primitive)});
        return ranges;
    }
    for(unsigned first=0;first<clips.size();) {
        unsigned count=step;
        bool full=FullScreenOverlay(clips.subspan(first,count),primitive);
        if(!full && primitive==4 && clips.size()-first>=6 &&
           FullScreenOverlay(clips.subspan(first,6),primitive)) {count=6;full=true;}
        ranges.push_back({first,count,full});
        first+=count;
    }
    return ranges;
}
constexpr std::array<uint32_t,2> HudExpandedIndexRange(uint32_t primitive,
                                                     uint32_t first,uint32_t count) {
    const unsigned step=primitive==13 ? 4 : primitive==8 ? 3 : 1;
    return {first/step*(step==1 ? 1 : 6),count/step*(step==1 ? 1 : 6)};
}
}
