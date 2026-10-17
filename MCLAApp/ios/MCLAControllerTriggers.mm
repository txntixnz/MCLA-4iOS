#import "MCLAControllerTriggers.h"
#include "MCLAControllerInput.h"
#include <array>
#include <mutex>

using mcla::input::TriggerRange;
static NSString* const ProfilesKey=@"MCLAControllerTriggerProfilesV1";
@interface MCLATriggerState : NSObject {
@public
    std::array<TriggerRange,2> range;
    std::array<float,2> minimum,maximum;
    std::array<uint8_t,2> guestMaximum;
    std::array<bool,2> seen,needsRelease;
    bool suspended;
}
@property(nonatomic,copy) NSString* identity;
@end
@implementation MCLATriggerState
- (instancetype)init {
    self=[super init];
    if(self) { range={TriggerRange{},TriggerRange{}};minimum={};maximum={};
        guestMaximum={};seen={};needsRelease={};suspended=false; }
    return self;
}
@end

namespace {
std::mutex stateMutex;
NSMapTable<GCController*,MCLATriggerState*>* States() {
    static NSMapTable* states=[NSMapTable weakToStrongObjectsMapTable];
    return states;
}
NSString* Identity(GCController* controller) {
    return [NSString stringWithFormat:@"%@|%@|%@",controller.vendorName ?: @"Unknown",
        controller.productCategory ?: @"Unknown",NSStringFromClass(controller.extendedGamepad.class) ?: @"Unknown"];
}
TriggerRange Decode(id encoded) {
    if(![encoded isKindOfClass:NSArray.class] || [encoded count]!=2 ||
       ![encoded[0] isKindOfClass:NSNumber.class] || ![encoded[1] isKindOfClass:NSNumber.class]) return {};
    TriggerRange range{[encoded[0] floatValue],[encoded[1] floatValue]};
    return range.Valid() ? range : TriggerRange{};
}
MCLATriggerState* State(GCController* controller) { // caller holds stateMutex
    MCLATriggerState* state=[States() objectForKey:controller];
    if(!state) {
        state=[[MCLATriggerState alloc] init];
        state.identity=Identity(controller);
        id profiles=[NSUserDefaults.standardUserDefaults objectForKey:ProfilesKey];
        id saved=[profiles isKindOfClass:NSDictionary.class] ? profiles[state.identity] : nil;
        if([saved isKindOfClass:NSDictionary.class]) {
            state->range[0]=Decode(saved[@"left"]);state->range[1]=Decode(saved[@"right"]);
        }
        [States() setObject:state forKey:controller];
    }
    return state;
}
void Save(GCController* controller,const std::array<TriggerRange,2>& ranges,bool reset) {
    std::lock_guard lock(stateMutex);
    NSString* identity=Identity(controller);
    id stored=[NSUserDefaults.standardUserDefaults objectForKey:ProfilesKey];
    NSMutableDictionary* profiles=[stored isKindOfClass:NSDictionary.class] ? [stored mutableCopy] : [NSMutableDictionary dictionary];
    if(reset) [profiles removeObjectForKey:identity];
    else profiles[identity]=@{@"left":@[@(ranges[0].released),@(ranges[0].full)],
                             @"right":@[@(ranges[1].released),@(ranges[1].full)]};
    [NSUserDefaults.standardUserDefaults setObject:profiles forKey:ProfilesKey];
    // Identical controller types intentionally share a calibration profile.
    for(MCLATriggerState* state in States().objectEnumerator)
        if([state.identity isEqual:identity]) {
            state->range=ranges;state->needsRelease={true,true};
        }
}
void Suspend(GCController* controller,bool suspended) {
    if(!controller) return;
    std::lock_guard lock(stateMutex);
    auto* state=State(controller);
    state->suspended=suspended;
    state->needsRelease={true,true};
}
}

extern "C" uint8_t MCLAControllerTriggerValue(void* rawController,bool right,float raw) {
    if(!rawController) return 0;
    GCController* controller=(__bridge GCController*)rawController;
    std::lock_guard lock(stateMutex);
    auto* state=State(controller);
    const unsigned i=right ? 1 : 0;
    if(std::isfinite(raw)) {
        if(!state->seen[i]) state->minimum[i]=state->maximum[i]=raw;
        else {
            state->minimum[i]=std::min(state->minimum[i],raw);
            state->maximum[i]=std::max(state->maximum[i],raw);
        }
        state->seen[i]=true;
    }
    if(state->suspended) return 0;
    if(state->needsRelease[i]) {
        if(std::isfinite(raw) && raw<=state->range[i].released+.02f) state->needsRelease[i]=false;
        return 0;
    }
    const uint8_t output=state->range[i].Convert(raw);
    state->guestMaximum[i]=std::max(state->guestMaximum[i],output);
    return output;
}

static NSString* TriggerDiagnostics(bool persist) {
    std::lock_guard lock(stateMutex);
    NSMutableArray* entries=[NSMutableArray array];
    for(MCLATriggerState* state in States().objectEnumerator) {
        NSMutableArray* triggers=[NSMutableArray array];
        for(unsigned i=0;i<2;++i)
            [triggers addObject:@{@"side":i ? @"right" : @"left",@"sampled":@(state->seen[i]),
                @"raw_min":@(state->minimum[i]),@"raw_max":@(state->maximum[i]),
                @"mapped_max":@(state->guestMaximum[i]),@"released":@(state->range[i].released),
                @"full":@(state->range[i].full)}];
        [entries addObject:@{@"controller_type":state.identity,@"triggers":triggers}];
    }
    NSDictionary* current=@{@"controllers":entries,@"recorded_at":NSDate.date.description,
        @"build":NSBundle.mainBundle.infoDictionary[@"CFBundleVersion"] ?: @"unknown",
        @"profiles":[NSUserDefaults.standardUserDefaults dictionaryForKey:ProfilesKey] ?: @{}};
    NSUserDefaults* defaults=NSUserDefaults.standardUserDefaults;
    if(persist && entries.count) [defaults setObject:current forKey:@"MCLAControllerTriggerLastSessionV1"];
    NSDictionary* previous=[defaults dictionaryForKey:@"MCLAControllerTriggerLastSessionV1"] ?: @{};
    NSData* data=[NSJSONSerialization dataWithJSONObject:@{@"current_process":current,@"last_background_snapshot":previous}
        options:NSJSONWritingPrettyPrinted error:nil];
    return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding] ?: @"unavailable";
}
NSString* MCLAControllerTriggerDiagnostics(void) { return TriggerDiagnostics(false); }
void MCLAPersistControllerTriggerDiagnostics(void) { (void)TriggerDiagnostics(true); }

@interface MCLATriggerSettingsController : UIViewController {
    std::array<TriggerRange,2> proposed;
}
@property(nonatomic,strong) GCController* controller;
@property(nonatomic,strong) UILabel* instruction;
@property(nonatomic,strong) UILabel* leftReadout;
@property(nonatomic,strong) UILabel* rightReadout;
@property(nonatomic,strong) UIProgressView* leftProgress;
@property(nonatomic,strong) UIProgressView* rightProgress;
@property(nonatomic,strong) UIButton* advance;
@property(nonatomic,strong) NSTimer* timer;
@property(nonatomic,assign) NSInteger step;
@property(nonatomic,assign) BOOL disconnected;
@end

@implementation MCLATriggerSettingsController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.title=@"Controller Triggers";
    self.view.backgroundColor=UIColor.systemGroupedBackgroundColor;
    self.instruction=[[UILabel alloc] init];self.instruction.numberOfLines=0;
    self.instruction.font=[UIFont preferredFontForTextStyle:UIFontTextStyleBody];
    self.leftReadout=[[UILabel alloc] init];self.rightReadout=[[UILabel alloc] init];
    for(UILabel* label in @[self.leftReadout,self.rightReadout]) {
        label.font=[UIFont monospacedDigitSystemFontOfSize:15 weight:UIFontWeightMedium];
        label.numberOfLines=0;
    }
    self.leftReadout.accessibilityIdentifier=@"mcla.triggers.left";
    self.rightReadout.accessibilityIdentifier=@"mcla.triggers.right";
    self.leftProgress=[[UIProgressView alloc] initWithProgressViewStyle:UIProgressViewStyleDefault];
    self.rightProgress=[[UIProgressView alloc] initWithProgressViewStyle:UIProgressViewStyleDefault];
    self.advance=[UIButton buttonWithType:UIButtonTypeSystem];
    self.advance.accessibilityIdentifier=@"mcla.triggers.advance";
    [self.advance addTarget:self action:@selector(advanceCalibration) forControlEvents:UIControlEventTouchUpInside];
    UIButton* reset=[UIButton buttonWithType:UIButtonTypeSystem];
    [reset setTitle:@"Reset to standard range" forState:UIControlStateNormal];
    [reset addTarget:self action:@selector(resetCalibration) forControlEvents:UIControlEventTouchUpInside];
    UIStackView* stack=[[UIStackView alloc] initWithArrangedSubviews:@[self.instruction,self.leftReadout,
        self.leftProgress,self.rightReadout,self.rightProgress,self.advance,reset]];
    stack.axis=UILayoutConstraintAxisVertical;stack.spacing=12;stack.translatesAutoresizingMaskIntoConstraints=NO;
    UIScrollView* scroll=[[UIScrollView alloc] init];scroll.translatesAutoresizingMaskIntoConstraints=NO;
    [self.view addSubview:scroll];[scroll addSubview:stack];
    [NSLayoutConstraint activateConstraints:@[
        [scroll.leadingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.leadingAnchor],
        [scroll.trailingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.trailingAnchor],
        [scroll.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor],
        [scroll.bottomAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.bottomAnchor],
        [stack.leadingAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.leadingAnchor constant:20],
        [stack.trailingAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.trailingAnchor constant:-20],
        [stack.topAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.topAnchor constant:16],
        [stack.bottomAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.bottomAnchor constant:-20],
        [stack.widthAnchor constraintEqualToAnchor:scroll.frameLayoutGuide.widthAnchor constant:-40]]];
    [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(disconnect:)
        name:GCControllerDidDisconnectNotification object:self.controller];
    [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(interrupted:)
        name:UIApplicationWillResignActiveNotification object:nil];
    [self cancelCalibration];
}
- (void)viewWillAppear:(BOOL)animated {
    [super viewWillAppear:animated];Suspend(self.controller,true);
    __weak MCLATriggerSettingsController* weakSelf=self;
    self.timer=[NSTimer scheduledTimerWithTimeInterval:.05 repeats:YES block:^(NSTimer* timer) {
        (void)timer;[weakSelf pollTriggers];
    }];
    [self pollTriggers];
}
- (void)viewWillDisappear:(BOOL)animated {
    [super viewWillDisappear:animated];[self.timer invalidate];self.timer=nil;
    [self cancelCalibration];Suspend(self.controller,false);
}
- (void)dealloc { [self.timer invalidate];[NSNotificationCenter.defaultCenter removeObserver:self]; }
- (void)cancelCalibration {
    self.step=0;
    self.instruction.text=self.controller ? @"Squeeze each trigger to check its range. If a full squeeze does not reach 100%, calibrate below. Throttle and brake stay at zero on this screen. Release both triggers after leaving. Calibration is saved for this controller type."
        : @"Connect your controller, then reopen this screen to check and calibrate its triggers.";
    [self.advance setTitle:@"Calibrate triggers" forState:UIControlStateNormal];
    self.advance.enabled=self.controller && !self.disconnected;
}
- (void)interrupted:(NSNotification*)note { (void)note;[self cancelCalibration]; }
- (void)disconnect:(NSNotification*)note {
    (void)note;self.disconnected=YES;[self cancelCalibration];
    self.instruction.text=@"Controller disconnected. Reconnect it, then reopen this screen. No unfinished calibration was saved.";
    [self pollTriggers];
}
- (void)pollTriggers {
    if(!self.controller || self.disconnected) {
        self.leftReadout.text=@"LT / L2: disconnected";self.rightReadout.text=@"RT / R2: disconnected";
        self.leftProgress.progress=0;self.rightProgress.progress=0;return;
    }
    const std::array<float,2> raw{self.controller.extendedGamepad.leftTrigger.value,
        self.controller.extendedGamepad.rightTrigger.value};
    std::array<TriggerRange,2> ranges;
    { std::lock_guard lock(stateMutex);ranges=State(self.controller)->range; }
    for(unsigned i=0;i<2;++i) {
        if(self.step==2 && std::isfinite(raw[i])) proposed[i].full=std::max(proposed[i].full,raw[i]);
        const auto output=(self.step==2 && proposed[i].Valid() ? proposed[i] : ranges[i]).Convert(raw[i]);
        UILabel* label=i ? self.rightReadout : self.leftReadout;
        label.text=[NSString stringWithFormat:@"%@: iOS %.0f%% → game %.0f%% (%u/255)",
            i ? @"RT / R2" : @"LT / L2",raw[i]*100.,output/2.55,output];
        (i ? self.rightProgress : self.leftProgress).progress=output/255.f;
    }
}
- (void)advanceCalibration {
    if(!self.controller || self.disconnected || UIApplication.sharedApplication.applicationState!=UIApplicationStateActive) return;
    if(self.step==0) {
        self.step=1;self.instruction.text=@"1. Take your fingers off both triggers, then tap Record released.";
        [self.advance setTitle:@"Record released" forState:UIControlStateNormal];return;
    }
    if(self.step==1) {
        proposed={TriggerRange{self.controller.extendedGamepad.leftTrigger.value,0},
                  TriggerRange{self.controller.extendedGamepad.rightTrigger.value,0}};
        for(auto& range:proposed) range.full=range.released;
        self.step=2;self.instruction.text=@"2. Squeeze LT / L2 fully and release it. Then squeeze RT / R2 fully and release it. Tap Save when both are done.";
        [self.advance setTitle:@"Save calibration" forState:UIControlStateNormal];return;
    }
    [self pollTriggers];
    if(!proposed[0].Valid() || !proposed[1].Valid()) {
        self.instruction.text=@"Both triggers need a full squeeze before saving. Squeeze and release each trigger, then tap Save again.";return;
    }
    Save(self.controller,proposed,false);[self cancelCalibration];
    self.instruction.text=@"Calibration saved. A full squeeze now sends 100% to the game. Release both triggers after leaving this screen.";
    [self pollTriggers];
}
- (void)resetCalibration {
    if(!self.controller || self.disconnected) return;
    Save(self.controller,{TriggerRange{},TriggerRange{}},true);[self cancelCalibration];[self pollTriggers];
}
@end

UIViewController* MCLACreateTriggerSettings(GCController* controller) {
    auto* view=[[MCLATriggerSettingsController alloc] init];view.controller=controller;return view;
}
