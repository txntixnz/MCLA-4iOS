#pragma once
#include <cstdint>
// Called with the actual controller owned by the native iOS input slot.
extern "C" uint8_t MCLAControllerTriggerValue(void* controller, bool right, float raw);
#ifdef __OBJC__
#import <UIKit/UIKit.h>
#import <GameController/GameController.h>
UIViewController* MCLACreateTriggerSettings(GCController* controller);
NSString* MCLAControllerTriggerDiagnostics(void);
void MCLAPersistControllerTriggerDiagnostics(void);
#endif
