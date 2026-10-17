// Shipping UIKit code with synthetic runtime/input recording. The only override
// is controller inventory; notifications and all visibility/input handlers are real.
#import "MCLAViewController.h"
#import <GameController/GameController.h>
#include "MCLABootstrapSubsystems.h"
#import "MCLAControllerTriggers.h"
#include <cassert>
#include <cmath>
uint16_t MCLAControlPreviewButtons();
bool MCLAControlPreviewRightTrigger();
bool MCLAControlPreviewLeftTrigger();
bool MCLAControlPreviewLeftStickActive();
bool MCLAControlPreviewRightStickActive();
@interface UIViewController (TriggerTest)
- (void)advanceCalibration;
- (void)pollTriggers;
- (void)resetCalibration;
- (void)interrupted:(NSNotification*)notification;
@end

static UIViewController* TestTriggerCalibration(void) {
    auto* pad=[GCController controllerWithExtendedGamepad];
    auto read=[&](bool right) {
        return MCLAControllerTriggerValue((__bridge void*)pad,right,
            right ? pad.extendedGamepad.rightTrigger.value : pad.extendedGamepad.leftTrigger.value);
    };
    [NSUserDefaults.standardUserDefaults removeObjectForKey:@"MCLAControllerTriggerProfilesV1"];
    for(float value:{0.f,.25f,.5f,.75f,1.f}) {
        [pad.extendedGamepad.leftTrigger setValue:value];
        [pad.extendedGamepad.rightTrigger setValue:1-value];
        assert(read(false)==std::lround(value*255) && read(true)==std::lround((1-value)*255));
    }
    UIViewController* page=MCLACreateTriggerSettings(pad);
    [page loadViewIfNeeded];[page viewWillAppear:NO];
    [pad.extendedGamepad.leftTrigger setValue:0];[pad.extendedGamepad.rightTrigger setValue:0];
    [page advanceCalibration];[page advanceCalibration];[page advanceCalibration];
    assert([[page valueForKey:@"step"] integerValue]==2); // no travel: reject Save
    [pad.extendedGamepad.leftTrigger setValue:.5f];[page pollTriggers];[page advanceCalibration];
    assert([[page valueForKey:@"step"] integerValue]==2); // both sides required
    [pad.extendedGamepad.leftTrigger setValue:0];
    [pad.extendedGamepad.rightTrigger setValue:.4f];[page pollTriggers];
    assert(read(false)==0 && read(true)==0); // guest pedals suspended in setup
    [page advanceCalibration];
    assert([[page valueForKey:@"step"] integerValue]==0);
    [page viewWillDisappear:NO];
    assert(read(true)==0); // held throttle cannot restart the car on Back
    [pad.extendedGamepad.rightTrigger setValue:0];assert(read(true)==0);
    [pad.extendedGamepad.rightTrigger setValue:.2f];assert(read(true)==128);
    [pad.extendedGamepad.rightTrigger setValue:.4f];assert(read(true)==255);
    [pad.extendedGamepad.leftTrigger setValue:0];assert(read(false)==0);
    [pad.extendedGamepad.leftTrigger setValue:.25f];assert(read(false)==128);
    [pad.extendedGamepad.leftTrigger setValue:.5f];assert(read(false)==255);
    // A new controller instance of the same type loads persisted endpoints.
    auto* reconnected=[GCController controllerWithExtendedGamepad];
    assert(MCLAControllerTriggerValue((__bridge void*)reconnected,true,.4f)==255);
    NSDictionary* saved=[NSUserDefaults.standardUserDefaults dictionaryForKey:@"MCLAControllerTriggerProfilesV1"];
    [page viewWillAppear:NO];[page advanceCalibration];[page advanceCalibration];
    [page interrupted:nil];
    assert([[page valueForKey:@"step"] integerValue]==0);
    assert([[NSUserDefaults.standardUserDefaults dictionaryForKey:@"MCLAControllerTriggerProfilesV1"] isEqual:saved]);
    [NSNotificationCenter.defaultCenter postNotificationName:GCControllerDidDisconnectNotification object:pad];
    assert([[page valueForKey:@"disconnected"] boolValue]);
    [page advanceCalibration];
    assert([[NSUserDefaults.standardUserDefaults dictionaryForKey:@"MCLAControllerTriggerProfilesV1"] isEqual:saved]);
    [page viewWillDisappear:NO];
    page=MCLACreateTriggerSettings(reconnected);[page loadViewIfNeeded];
    [page resetCalibration];
    assert(MCLAControllerTriggerValue((__bridge void*)reconnected,true,1)==0);
    assert(MCLAControllerTriggerValue((__bridge void*)reconnected,true,0)==0);
    assert(MCLAControllerTriggerValue((__bridge void*)reconnected,true,.5f)==128);
    // Build a real UIKit preview of the saved half-range repair.
    [reconnected.extendedGamepad.leftTrigger setValue:0];
    [reconnected.extendedGamepad.rightTrigger setValue:0];
    [page advanceCalibration];[page advanceCalibration];
    [reconnected.extendedGamepad.leftTrigger setValue:.5f];
    [reconnected.extendedGamepad.rightTrigger setValue:.4f];
    [page pollTriggers];[page advanceCalibration];
    assert([((UILabel*)[page valueForKey:@"rightReadout"]).text containsString:@"255/255"]);
    NSLog(@"MCLA_TRIGGER_TEST PASS: real GameController snapshots, independent analog ranges, partial-save rejection, persisted reconnect, suspended pedals, release rearm, interruption/disconnect cancellation and reset");
    return page;
}
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
- (void)showControlsOptions:(id)sender;
- (void)dragTouchControl:(UIPanGestureRecognizer*)pan;
- (void)applyTouchLayout;
@end
@interface ControllerPreviewDrag : UIPanGestureRecognizer
@property(nonatomic,assign) CGPoint movement;
@end
@implementation ControllerPreviewDrag
- (CGPoint)translationInView:(UIView*)view { (void)view; return self.movement; }
- (void)setTranslation:(CGPoint)translation inView:(UIView*)view { (void)view; self.movement=translation; }
- (UIGestureRecognizerState)state { return UIGestureRecognizerStateEnded; }
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
    UIViewController* triggers=TestTriggerCalibration();
    UINavigationController* navigation=[[UINavigationController alloc] initWithRootViewController:triggers];
    navigation.overrideUserInterfaceStyle=UIUserInterfaceStyleDark;
    navigation.modalPresentationStyle=UIModalPresentationFormSheet;
    [self presentViewController:navigation animated:NO completion:^{
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_SEC),dispatch_get_main_queue(),^{
            UIGraphicsImageRenderer* renderer=[[UIGraphicsImageRenderer alloc] initWithSize:self.view.window.bounds.size];
            UIImage* image=[renderer imageWithActions:^(UIGraphicsImageRendererContext* context) {
                (void)context;[self.view.window drawViewHierarchyInRect:self.view.window.bounds afterScreenUpdates:YES];
            }];
            NSString* docs=NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,NSUserDomainMask,YES).firstObject;
            assert([UIImagePNGRepresentation(image) writeToFile:[docs stringByAppendingPathComponent:@"controller-triggers.png"] atomically:YES]);
            [self dismissViewControllerAnimated:NO completion:^{ [self testSettingsEntry]; }];
        });
    }];
}
- (void)testSettingsEntry {
    [self notifyController:NO];
    [self showControlsOptions:nil];
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_SEC),dispatch_get_main_queue(),^{
        UINavigationController* navigation=(UINavigationController*)self.presentedViewController;
        assert([navigation isKindOfClass:UINavigationController.class]);
        UITableViewController* options=(UITableViewController*)navigation.topViewController;
        UITableViewCell* triggerRow=[options.tableView.dataSource tableView:options.tableView
            cellForRowAtIndexPath:[NSIndexPath indexPathForRow:0 inSection:3]];
        assert([triggerRow.accessibilityIdentifier isEqual:@"mcla.controls.triggerCalibration"]);
        NSIndexPath* edit=[NSIndexPath indexPathForRow:0 inSection:1];
        UITableViewCell* row=[options.tableView.dataSource tableView:options.tableView cellForRowAtIndexPath:edit];
        assert([row.accessibilityIdentifier isEqual:@"mcla.controls.editTouchLayout"]);
        [options.tableView.delegate tableView:options.tableView didSelectRowAtIndexPath:edit];
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_SEC),dispatch_get_main_queue(),^{ [self testEditorThenGameplay]; });
    });
}
- (void)testEditorThenGameplay {
    assert(!self.presentedViewController);
    assert([[self valueForKey:@"editingTouchLayout"] boolValue]);
    assert(![[self valueForKey:@"gameVisible"] boolValue]);
    assert(((UIView*)[self valueForKey:@"panel"]).hidden);
    assert(!((UIView*)[self valueForKey:@"touchControls"]).hidden);
    assert(![self valueForKey:@"toolbarTimer"]);
    UIButton* done=[self valueForKey:@"editButton"];
    assert(!done.hidden && [done.currentTitle isEqual:@"DONE"]);
    [self.view layoutIfNeeded];
    NSDictionary* controls=[self valueForKey:@"layoutControls"];
    UIButton* pause=controls[@"pause"];
    const CGPoint original=pause.center;
    ControllerPreviewDrag* drag=[[ControllerPreviewDrag alloc] init];
    drag.movement=CGPointMake(-25,-35);
    [pause addGestureRecognizer:drag];
    [self dragTouchControl:drag];
    assert(fabs(pause.center.x-original.x+25)<1 && fabs(pause.center.y-original.y+35)<1);
    [pause removeGestureRecognizer:drag];
    [self gamepadButtonDown:pause]; [self assertNeutral];
    [done sendActionsForControlEvents:UIControlEventTouchUpInside];
    assert(![[self valueForKey:@"editingTouchLayout"] boolValue]);
    assert(!((UIView*)[self valueForKey:@"panel"]).hidden);
    [self applyTouchLayout]; [self.view layoutIfNeeded];
    assert(fabs(pause.center.y-original.y+35)<1);
    [self toggleTouchLayoutEditing:nil];
    assert(fabs(pause.center.y-original.y+35)<1);
    [done sendActionsForControlEvents:UIControlEventTouchUpInside];
    NSUserDefaults* defaults=NSUserDefaults.standardUserDefaults;
    [defaults setBool:NO forKey:@"MCLATouchEnabledControlOverhaulTest"];
    [self toggleTouchLayoutEditing:nil];
    [self refreshBringupStatus];
    assert([[self valueForKey:@"editingTouchLayout"] boolValue]);
    assert(![defaults boolForKey:@"MCLATouchEnabledControlOverhaulTest"]);
    [done sendActionsForControlEvents:UIControlEventTouchUpInside];
    [defaults setBool:YES forKey:@"MCLATouchEnabledControlOverhaulTest"];
    [self resetTouchLayout];
    [self notifyController:YES];
    [self runGameplayTests];
}
- (void)runGameplayTests {
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
    for(NSString* key in @[@"gps",@"pause"])
        assert(CGRectGetMinY(((UIView*)controls[key]).frame)>CGRectGetMinY(safe)+safe.size.height*.8);
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
    assert(!((UIView*)[self valueForKey:@"touchControls"]).hidden);
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
    assert(([[defaults dictionaryForKey:@"MCLATouchLayoutPositionsOverhaul"] isEqual:@{@"steer":@[@.35,@.60]}]));
    assert([[defaults arrayForKey:@"MCLATouchActiveControlsXbox"] count]==14);
    [@"MCLA_CONTROLLER_UI_TEST PASS\n" writeToFile:[documents stringByAppendingPathComponent:@"controller-ui-result.txt"] atomically:YES encoding:NSUTF8StringEncoding error:nil];
    NSLog(@"MCLA_CONTROLLER_UI_TEST PASS: settings editor entry before launch, drag/save/reopen, disabled-touch preview, bottom Start/View, preconnected pad, hot connect/disconnect, held-input release, late-event rejection, edit/background safety, Xbox buttons/spacing/artwork and saved-layout isolation");
    exit(0);
}
@end
UIViewController* MCLACreateLauncherTestController(void) {
    // Match an already configured installation; the unrelated first-run folder
    // alert would otherwise occupy the settings presentation slot.
    NSString* documents=NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,NSUserDomainMask,YES).firstObject;
    [NSFileManager.defaultManager createDirectoryAtPath:[documents stringByAppendingPathComponent:@"MCLA_Game_Files"]
        withIntermediateDirectories:YES attributes:nil error:nil];
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
