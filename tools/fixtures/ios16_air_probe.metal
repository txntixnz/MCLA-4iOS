#include <metal_stdlib>
using namespace metal;
constant uint flags [[function_constant(0)]];
struct Heap { texture2d<float> tex; };
struct Samplers { sampler value; };
struct Constants { ulong address; };
struct Varyings { float4 position [[position]]; float2 uv; };
struct Attributes { float4 position [[attribute(0)]]; float2 uv [[attribute(1)]]; };
vertex Varyings vertexProbe(Attributes input [[stage_in]],
                           constant Constants& constants [[buffer(8)]]) {
    float4 scale = *reinterpret_cast<device float4*>(constants.address);
    return {input.position * scale, input.uv};
}
fragment float4 probe(Varyings input [[stage_in]],
                      constant Heap* heap [[buffer(0)]],
                      constant Samplers* samplers [[buffer(4)]],
                      constant Constants& constants [[buffer(8)]]) {
    float4 value = *reinterpret_cast<device float4*>(constants.address);
    float4 color = heap[0].tex.sample(samplers[0].value, input.uv);
    if (is_function_constant_defined(flags) && (flags & 1)) color = saturate(color);
    return value * color;
}
