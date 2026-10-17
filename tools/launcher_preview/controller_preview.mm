// Shipping UIKit code with synthetic runtime/input recording. The only override
// is controller inventory; notifications and all visibility/input handlers are real.
#import "MCLAViewController.h"
#import <GameController/GameController.h>
#include "MCLABootstrapSubsystems.h"
#include <cassert>
uint16_t MCLAControlPreviewButtons();
bool MCLAControlPreviewRightTrigger();
bool MCLAControlPreviewLeftTrigger();
bool MCLAControlPreviewLeftStickActive();
bool MCLAControlPreviewRightStickActive();
@interface MCLAViewController (ControllerTest)
- (GCController*)connectedGameController;
- (void)refreshBringupStatus;
- (void)refreshTouchInputForGameVisible:(BOOL)visible;
- (void)launchMCLA:(id)sender;
- (void)gamepadButtonDown:(UIButton*)button;
- (void)gamepadButtonUp:(UIButton*)button;
- (void)pedalDown:(UIButton*)button;
- (void)pedalUp:(UIButton*)button;
- (void)toggleTouchLayoutEditing:(id)sender;
- (void)appWillResignActive:(NSNotification*)notification;
- (void)appDidBecomeActive:(NSNotification*)notification;
- (void)resetTouchLayout;
@end
@interface ControllerPreview : MCLAViewController
@property(nonatomic,strong) GCController* testPad;
@property(nonatomic,assign) BOOL startedTests;
@end
@implementation ControllerPreview
- (GCController*)connectedGameController { return self.testPad; }
- (UIInterfaceOrientationMask)supportedInterfaceOrientations { return UIInterfaceOrientationMaskLandscape; }
- (void)viewDidAppear:(BOOL)animated {
    [super viewDidAppear:animated];
    if(self.startedTests) return;
    self.startedTests=YES;
    [self.view.window.windowScene requestGeometryUpdateWithPreferences:
        [[UIWindowSceneGeometryPreferencesIOS alloc] initWithInterfaceOrientations:UIInterfaceOrientationMaskLandscapeRight]
        errorHandler:nil];
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC),dispatch_get_main_queue(),^{ [self runTests]; });
}
- (void)notifyController:(BOOL)connected {
    GCController* old=self.testPad;
    self.testPad=connected ? [GCController controllerWithExtendedGamepad] : nil;
    [NSNotificationCenter.defaultCenter postNotificationName:connected ? GCControllerDidConnectNotification : GCControllerDidDisconnectNotification
        object:connected ? self.testPad : old];
}
- (void)assertNeutral {
    assert(!MCLAControlPreviewButtons() && !MCLAControlPreviewRightTrigger() && !MCLAControlPreviewLeftTrigger());
    assert(!MCLAControlPreviewLeftStickActive() && !MCLAControlPreviewRightStickActive());
}
- (void)assertHidden {
    assert(![[self valueForKey:@"touchInputActive"] boolValue]);
    for(UIView* control in [[self valueForKey:@"layoutControls"] allValues]) assert(control.hidden);
    assert(((UIView*)[self valueForKey:@"fullPadPanel"]).hidden);
    assert(((UIView*)[self valueForKey:@"slideControls"]).hidden);
    [self assertNeutral];
}
- (void)runTests {
    assert(self.view.bounds.size.width>self.view.bounds.size.height);
    [self launchMCLA:nil]; [self refreshBringupStatus];
    assert([[self valueForKey:@"gameVisible"] boolValue]);
    [self assertHidden]; // already connected at launch
    [self notifyController:NO];
    assert([[self valueForKey:@"touchInputActive"] boolValue]);
    [self.view layoutIfNeeded];
    NSDictionary* controls=[self valueForKey:@"layoutControls"];
    for(NSString* key in @[@"steer",@"look",@"handbrake",@"weight",@"nitro",@"headlights",@"gas",@"brake",@"hud",@"hydraulics",@"track_left",@"track_right",@"gps",@"pause",@"ability",@"camera",@"info",@"horn"])
        assert(!((UIView*)controls[key]).hidden);
    UIButton* a=controls[@"handbrake"],*b=controls[@"weight"],*x=controls[@"nitro"],*y=controls[@"headlights"];
    assert(a.tag==MCLA_GAMEPAD_A && b.tag==MCLA_GAMEPAD_B && x.tag==MCLA_GAMEPAD_X && y.tag==MCLA_GAMEPAD_Y);
    assert([[a valueForKey:@"artworkKey"] isEqual:@"xbox_A"]);
    assert(a.center.y>b.center.y && b.center.x>a.center.x && x.center.x<a.center.x && y.center.y<b.center.y);
    CGRect safe=UIEdgeInsetsInsetRect(self.view.bounds,self.view.safeAreaInsets);
    NSMutableArray<UIView*>* visible=[NSMutableArray array];
    for(UIView* control in controls.allValues) if(!control.hidden) {
        assert(CGRectContainsRect(safe,control.frame));
        for(UIView* other in visible) assert(!CGRectIntersectsRect(control.frame,other.frame));
        [visible addObject:control];
    }
    // Capture actual UIKit artwork before the physical-pad takeover.
    UIGraphicsImageRenderer* renderer=[[UIGraphicsImageRenderer alloc] initWithSize:self.view.bounds.size];
    UIImage* image=[renderer imageWithActions:^(UIGraphicsImageRendererContext* context) {
        (void)context; [self.view drawViewHierarchyInRect:self.view.bounds afterScreenUpdates:YES];
    }];
    NSString* documents=NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,NSUserDomainMask,YES).firstObject;
    assert([UIImagePNGRepresentation(image) writeToFile:[documents stringByAppendingPathComponent:@"xbox-touch-layout.png"] atomically:YES]);
    [self gamepadButtonDown:a];
    assert(MCLAControlPreviewButtons() & MCLA_GAMEPAD_A);
    assert(!MCLAControlPreviewRightTrigger()); // standard A does not add throttle
    [self pedalDown:controls[@"gas"]]; [self pedalDown:controls[@"brake"]];
    void (^left)(float,float,BOOL)=[controls[@"steer"] valueForKey:@"onStick"];
    void (^right)(float,float,BOOL)=[controls[@"look"] valueForKey:@"onStick"];
    left(.5f,.2f,YES); right(-.3f,.4f,YES);
    assert(MCLAControlPreviewRightTrigger() && MCLAControlPreviewLeftTrigger());
    assert(MCLAControlPreviewLeftStickActive() && MCLAControlPreviewRightStickActive());
    [self notifyController:YES]; [self assertHidden];
    // Queued UIKit events must not reactivate virtual input after takeover.
    [self gamepadButtonDown:a]; [self pedalDown:controls[@"gas"]];
    left(1,1,YES);right(1,1,YES);[self assertNeutral];
    [self notifyController:NO];[self assertNeutral];
    assert([[self valueForKey:@"touchInputActive"] boolValue]);
    [self toggleTouchLayoutEditing:nil]; assert([[self valueForKey:@"editingTouchLayout"] boolValue]);
    [self notifyController:YES];[self assertHidden];
    assert(![[self valueForKey:@"editingTouchLayout"] boolValue]);
    [self notifyController:NO];
    [self appWillResignActive:nil];[self assertHidden];
    [self appDidBecomeActive:nil]; assert([[self valueForKey:@"touchInputActive"] boolValue]);
    NSUserDefaults* defaults=NSUserDefaults.standardUserDefaults;
    [defaults setBool:NO forKey:@"MCLATouchEnabledControlOverhaulTest"];
    [self notifyController:YES];[self notifyController:NO];[self assertHidden];
    [defaults setBool:YES forKey:@"MCLATouchEnabledControlOverhaulTest"];
    [self refreshTouchInputForGameVisible:YES];
    [self resetTouchLayout];
    assert([[defaults dictionaryForKey:@"MCLATouchLayoutPositionsOverhaul"] isEqual:@{@"steer":@[@.35,@.60]}]);
    assert([[defaults arrayForKey:@"MCLATouchActiveControlsXbox"] count]==14);
    NSLog(@"MCLA_CONTROLLER_UI_TEST PASS: preconnected pad, hot connect/disconnect, held-input release, late-event rejection, edit/background safety, disabled-touch preference, Xbox buttons/spacing/artwork and saved-layout isolation");
    exit(0);
}
@end
UIViewController* MCLACreateLauncherTestController(void) {
    NSUserDefaults* defaults=NSUserDefaults.standardUserDefaults;
    [defaults setBool:YES forKey:@"MCLAXboxTouchLayoutEnabled"];
    [defaults setBool:YES forKey:@"MCLATouchEnabledControlOverhaulTest"];
    [defaults setBool:NO forKey:@"MCLATiltEnabled"];
    [defaults setBool:NO forKey:@"MCLAFullPadVisible"];
    [defaults setObject:@{@"steer":@[@.35,@.60]} forKey:@"MCLATouchLayoutPositionsOverhaul"];
    ControllerPreview* controller=[[ControllerPreview alloc] init];
    controller.testPad=[GCController controllerWithExtendedGamepad];
    return controller;
}
