#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
int main(int argc, const char **argv) {
 @autoreleasepool {
  if (argc != 2) return 2;
  pid_t target = (pid_t)atoi(argv[1]);
  NSArray *windows = CFBridgingRelease(CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, kCGNullWindowID));
  NSMutableArray *found = [NSMutableArray array];
  for (NSDictionary *w in windows) {
   if ([w[(__bridge NSString*)kCGWindowOwnerPID] intValue] != target || [w[(__bridge NSString*)kCGWindowLayer] intValue] != 0) continue;
   NSDictionary *bounds = w[(__bridge NSString*)kCGWindowBounds];
   if ([bounds[@"Width"] doubleValue] < 10 || [bounds[@"Height"] doubleValue] < 10) continue;
   [found addObject:@{@"pid":@(target), @"bounds":bounds}];
  }
  NSData *json = [NSJSONSerialization dataWithJSONObject:found options:0 error:nil];
  fwrite(json.bytes,1,json.length,stdout); puts("");
 }
 return 0;
}
