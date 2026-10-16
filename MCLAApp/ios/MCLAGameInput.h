#pragma once
#import <Foundation/Foundation.h>
// Read-only identity check for extracted XEX files and XEX extents in an ISO.
NSString* MCLAVerifySelectedExecutable(NSURL* url, BOOL* verified);
