#import "MCLAGameInput.h"
#import <CommonCrypto/CommonDigest.h>
#include "MCLAISOReader.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <string>

/* Diagnostic only: fingerprint a user-selected executable without uploading it.
   Keep the game archives on the user's own device. */
NSString* MCLAVerifySelectedExecutable(NSURL* url, BOOL* verified) {
    if (verified) *verified = NO;
    const BOOL iso = [url.pathExtension.lowercaseString isEqualToString:@"iso"];
    if (!iso && ![[url.lastPathComponent lowercaseString] isEqualToString:@"default.xex"])
        return @"Select your Xbox 360 Complete Edition ISO, or extracted default.xex.";
    MCLAXexExtent extent = {};
    if (iso) {
        std::string problem;
        if (!MCLAFindXbox360Xex(url.fileSystemRepresentation, &extent, &problem))
            return [NSString stringWithUTF8String:problem.c_str()];
    }

    NSURL* manifestURL = [NSBundle.mainBundle URLForResource:@"GameDataManifest" withExtension:@"json"];
    NSData* data = manifestURL ? [NSData dataWithContentsOfURL:manifestURL] : nil;
    NSDictionary* manifest = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
    if (![manifest isKindOfClass:NSDictionary.class])
        return @"The bundled game-compatibility manifest is missing or invalid.";

    // For ISO images, hash ONLY default.xex in place; never copy/extract the ISO.
    FILE* file = fopen(url.fileSystemRepresentation, "rb");
    if (!file) return @"Unable to open the file. Save the ISO locally in Files first.";
    if (fseeko(file, 0, SEEK_END) != 0) { fclose(file); return @"Cannot determine file size."; }
    const off_t end = ftello(file);
    if (end <= 0) { fclose(file); return @"File is empty or unreadable."; }
    const uint64_t start = iso ? extent.offset : 0;
    const uint64_t length = iso ? extent.size : uint64_t(end);
    if (start > uint64_t(end) || length > uint64_t(end)-start ||
        fseeko(file, off_t(start), SEEK_SET) != 0) {
        fclose(file); return @"The executable extent is outside the file.";
    }
    char signature[4]={};
    if (length < 4 || fread(signature, 1, 4, file)!=4 ||
        memcmp(signature, "XEX2", 4) || fseeko(file, off_t(start), SEEK_SET) != 0) {
        fclose(file); return @"Xbox 360 default.xex has an invalid XEX2 header.";
    }
    CC_SHA256_CTX context; CC_SHA256_Init(&context);
    uint8_t block[65536]; uint64_t remaining = length;
    while (remaining) {
        size_t want = size_t(std::min<uint64_t>(remaining,sizeof(block)));
        size_t got = fread(block,1,want,file);
        if (got != want) {
            fclose(file);
            return @"Unable to read the game ISO completely. Ensure it is downloaded.";
        }
        CC_SHA256_Update(&context, block, (CC_LONG)got);
        remaining -= got;
    }
    fclose(file);
    unsigned char hash[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256_Final(hash, &context);
    NSMutableString* digest = [NSMutableString stringWithCapacity:CC_SHA256_DIGEST_LENGTH*2];
    for (uint8_t byte : hash) [digest appendFormat:@"%02x", byte];

    NSString* baseline = manifest[@"baselineDefaultXexSha256"];
    if ([baseline isKindOfClass:NSString.class] &&
        [digest caseInsensitiveCompare:baseline] == NSOrderedSame) {
        if (verified) *verified = YES;
        return [NSString stringWithFormat:
            @"Verified Xbox 360 Complete Edition: baseline game executable (media 5940C9DB).\\nSHA-256: %@\\n\\nThis confirms executable identity only, not a playable iOS runtime.",
            digest];
    }
    NSArray* alternatives = manifest[@"compatibleExecutables"];
    for (NSDictionary* candidate in alternatives) {
        if (![candidate isKindOfClass:NSDictionary.class]) continue;
        NSString* candidateHash = candidate[@"defaultXexSha256"];
        if ([candidateHash isKindOfClass:NSString.class] &&
            [digest caseInsensitiveCompare:candidateHash] == NSOrderedSame) {
            if (verified) *verified = YES;
            return [NSString stringWithFormat:
                @"Verified Xbox 360 Complete Edition executable. Alternate media ID: %@, version %@.\\nSHA-256: %@\\n\\nThis confirms executable identity only, not a playable iOS runtime.",
                candidate[@"mediaId"] ?: @"unknown", candidate[@"version"] ?: @"unknown", digest];
        }
    }
    return [NSString stringWithFormat:
        @"This default.xex does not match either executable supported by the existing recompilation. It could be another version or an updated executable.\\nSHA-256: %@\\n\\nDo not rename or patch it to bypass this check.", digest];
}

