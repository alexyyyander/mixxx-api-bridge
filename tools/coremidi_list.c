#include <CoreMIDI/CoreMIDI.h>
#include <CoreFoundation/CoreFoundation.h>
#include <stdio.h>

static void print_endpoint(const char* kind, ItemCount index, MIDIEndpointRef endpoint) {
    CFStringRef name = NULL;
    OSStatus status = MIDIObjectGetStringProperty(endpoint, kMIDIPropertyName, &name);
    char text[512] = {0};
    if (status == noErr && name != NULL) {
        CFStringGetCString(name, text, sizeof(text), kCFStringEncodingUTF8);
        CFRelease(name);
    }
    printf("%s[%lu]=%s\n", kind, (unsigned long)index, text);
}

int main(void) {
    ItemCount sources = MIDIGetNumberOfSources();
    ItemCount destinations = MIDIGetNumberOfDestinations();
    printf("sources=%lu destinations=%lu\n", (unsigned long)sources, (unsigned long)destinations);
    for (ItemCount i = 0; i < sources; ++i) {
        print_endpoint("source", i, MIDIGetSource(i));
    }
    for (ItemCount i = 0; i < destinations; ++i) {
        print_endpoint("destination", i, MIDIGetDestination(i));
    }
    return 0;
}
