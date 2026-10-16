#include "MCLAISOReader.h"
#include <array>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
#include <unordered_set>
#include <vector>

namespace {
uint16_t le16(const unsigned char* b) { return uint16_t(b[0]) | uint16_t(b[1])<<8; }
uint32_t le32(const unsigned char* b) { return uint32_t(le16(b)) | uint32_t(le16(b+2))<<16; }
struct Reader {
    FILE* f = nullptr; uint64_t size = 0;
    ~Reader() { if(f) fclose(f); }
    bool read(uint64_t at,void* dst,size_t n) {
        if(!f || at>size || uint64_t(n)>size-at || at>uint64_t(std::numeric_limits<off_t>::max())) return false;
        return fseeko(f,off_t(at),SEEK_SET)==0 && fread(dst,1,n,f)==n;
    }
};
bool fail(std::string* error,const char* what){ if(error) *error=what; return false; }
}
bool MCLAFindXbox360Xex(const char* isoPath,MCLAXexExtent* output,std::string* error){
    if(output) *output={};
    if(!isoPath || !output) return fail(error,"Invalid file reference.");
    Reader r; r.f=fopen(isoPath,"rb");
    if(!r.f) return fail(error,"ISO cannot be opened. Download it locally in the Files app first.");
    if(fseeko(r.f,0,SEEK_END)!=0) return fail(error,"ISO size is unavailable.");
    off_t end=ftello(r.f); if(end<0) return fail(error,"Invalid ISO length.");
    r.size=uint64_t(end);
    constexpr char magic[]="MICROSOFT*XBOX*MEDIA";
    constexpr uint64_t offsets[]={0,0xFB20,0x20600,0x2080000,0xFD90000};
    uint64_t part=0; bool found=false;
    for(uint64_t candidate:offsets){
        unsigned char first[20],last[20];
        if(r.read(candidate+65536,first,20) && r.read(candidate+65536+2028,last,20) &&
            memcmp(first,magic,20)==0 && memcmp(last,magic,20)==0){
            part=candidate; found=true; break;
        }
    }
    if(!found) return fail(error,"Not a supported raw Xbox 360 XDVDFS ISO. PS3 discs, compressed archives and some repacked ISOs are unsupported.");
    unsigned char root[8];
    if(!r.read(part+65536+20,root,8)) return fail(error,"Xbox disc root header is unreadable.");
    const uint64_t base=part+uint64_t(le32(root))*2048;
    const uint64_t len=le32(root+4);
    if(len<14 || len>32ull*1024*1024 || base>r.size || len>r.size-base)
        return fail(error,"Malformed Xbox disc directory.");
    struct Node{uint32_t at;};
    std::vector<Node> pending={{0}};
    std::unordered_set<uint32_t> visited;
    constexpr const char* names[]={"default.xex","xarchive_audio.rpf","xarchive_audlo.rpf","xarchive_cache.rpf","xarchive_music.rpf"};
    bool present[5]={};
    while(!pending.empty()){
        uint32_t at=pending.back().at;pending.pop_back();
        if(visited.size()>=500000 || uint64_t(at)>len || len-at<14 || !visited.insert(at).second)
            return fail(error,"Xbox disc directory contains an invalid pointer or cycle.");
        unsigned char b[14]={};if(!r.read(base+at,b,14))return fail(error,"Truncated Xbox directory entry.");
        uint8_t count=b[13];
        if(!count || count>len-at-14) return fail(error,"Invalid Xbox filename size.");
        unsigned char raw[255]={};if(!r.read(base+at+14,raw,count))return fail(error,"Truncated Xbox filename.");
        std::string name; name.reserve(count);
        for(unsigned i=0;i<count;i++){
            unsigned char c=raw[i];
            if(c<33 || c>126 || c=='/' || c=='\\' || c==':')return fail(error,"Invalid Xbox filename.");
            name.push_back(c>='A'&&c<='Z'?char(c+32):char(c));
        }
        if(name=="default.xexp")return fail(error,"Unverified default.xexp title update in Xbox ISO.");
        uint16_t left=le16(b),right=le16(b+2);
        if(left)pending.push_back({uint32_t(left)*4});
        if(right)pending.push_back({uint32_t(right)*4});
        const uint64_t entryOffset=part+uint64_t(le32(b+4))*2048;
        const uint64_t entryLen=le32(b+8);
        if(entryOffset>r.size || entryLen>r.size-entryOffset)
            return fail(error,"Xbox ISO contains an out-of-bounds extent.");
        if((b[12]&0x10)==0 && entryLen>0){
            for(int i=0;i<5;i++)if(name==names[i]){
                if(present[i])return fail(error,"Duplicate essential Xbox game file.");
                present[i]=true;
                if(i==0){output->offset=entryOffset;output->size=entryLen;}
            }
        }
    }
    if(!present[0])return fail(error,"Xbox ISO does not contain default.xex in its root.");
    for(int i=1;i<5;i++)if(!present[i])return fail(error,"Xbox Complete Edition archive files are missing.");
    if(output->size>128ull*1024*1024)return fail(error,"Unexpectedly large default.xex (over 128 MB).");
    return true;
}
