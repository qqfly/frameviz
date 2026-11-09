#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ApplicationServices/ApplicationServices.h>
static AXUIElementRef findGuide(AXUIElementRef element, int depth) {
 if (depth > 6) return NULL;
 CFTypeRef title = NULL;
 if (AXUIElementCopyAttributeValue(element, kAXTitleAttribute, &title) == kAXErrorSuccess && title) {
  bool matches = CFGetTypeID(title) == CFStringGetTypeID() && CFEqual(title, CFSTR("使用指南"));
  CFRelease(title);
  if (matches) { CFRetain(element); return element; }
 }
 CFTypeRef children = NULL;
 AXUIElementRef found = NULL;
 if (AXUIElementCopyAttributeValue(element, kAXChildrenAttribute, &children) == kAXErrorSuccess && children) {
  for (CFIndex i = 0; i < CFArrayGetCount(children) && !found; ++i) found = findGuide((AXUIElementRef)CFArrayGetValueAtIndex(children, i), depth + 1);
  CFRelease(children);
 }
 return found;
}
int main(int argc, const char **argv) {
 @autoreleasepool {
  if (argc != 2 && argc != 3) return 2;
  pid_t target = (pid_t)atoi(argv[1]);
  if (target <= 0) return 2;
  if (argc == 3 && strcmp(argv[2], "--guide") == 0) {
   if (!AXIsProcessTrusted()) { puts("{\"available\":false}"); return 0; }
   AXUIElementRef app = AXUIElementCreateApplication(target);
   CFTypeRef bar = NULL;
   AXError result = AXUIElementCopyAttributeValue(app, kAXMenuBarAttribute, &bar);
   AXUIElementRef guide = bar ? findGuide((AXUIElementRef)bar, 0) : NULL;
   if (guide) { result = AXUIElementPerformAction(guide, kAXPressAction); CFRelease(guide); }
   else { result = kAXErrorNoValue; }
   if (bar) CFRelease(bar);
   CFRelease(app);
   printf("{\"available\":true,\"opened\":%s,\"error\":%d}\n", result == kAXErrorSuccess ? "true" : "false", result);
   return 0;
  }
  if (argc == 3 && strcmp(argv[2], "--close") == 0) {
   if (!AXIsProcessTrusted()) { puts("{\"available\":false}"); return 0; }
   AXUIElementRef app = AXUIElementCreateApplication(target);
   CFTypeRef list = NULL;
   AXError result = AXUIElementCopyAttributeValue(app, kAXWindowsAttribute, &list);
   if (result == kAXErrorSuccess && list && CFArrayGetCount(list) > 0) {
    AXUIElementRef window = (AXUIElementRef)CFArrayGetValueAtIndex(list, 0);
    CFTypeRef button = NULL;
    result = AXUIElementCopyAttributeValue(window, kAXCloseButtonAttribute, &button);
    if (result == kAXErrorSuccess && button) {
     result = AXUIElementPerformAction(button, kAXPressAction);
     CFRelease(button);
    }
   } else if (result == kAXErrorSuccess) { result = kAXErrorNoValue; }
   if (list) CFRelease(list);
   CFRelease(app);
   printf("{\"available\":true,\"closed\":%s,\"error\":%d}\n", result == kAXErrorSuccess ? "true" : "false", result);
   return 0;
  }
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
