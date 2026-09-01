// Minimal CoreMIDI virtual-port helper for the Mixxx API Bridge.
//
// This deliberately avoids RtMidi/python-rtmidi. RtMidi's CoreMIDI backend
// can throw a C++ exception across its Cython boundary when the host rejects a
// MIDI client, which terminates Python. CoreMIDI reports an OSStatus instead.
//
// Protocol (one line at a time):
//   READY <source-name> <destination-name>\n
//   SEND <hex bytes>\n       inject bytes into the virtual source
//   RECV <hex bytes>\n       bytes received by the virtual destination
//   QUIT\n
#include <CoreMIDI/CoreMIDI.h>
#include <CoreFoundation/CoreFoundation.h>
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE 16384
#define MAX_PACKET 4096

typedef struct {
    MIDIClientRef client;
    MIDIEndpointRef source;
    MIDIEndpointRef destination;
    pthread_mutex_t output_lock;
} Bridge;

static void print_hex(FILE* stream, const Byte* data, UInt16 length) {
    for (UInt16 i = 0; i < length; ++i) {
        fprintf(stream, "%02X", data[i]);
    }
}

static void read_proc(const MIDIPacketList* packet_list,
        void* read_proc_ref_con,
        void* source_conn_ref_con) {
    (void)source_conn_ref_con;
    Bridge* bridge = (Bridge*)read_proc_ref_con;
    const MIDIPacket* packet = &packet_list->packet[0];

    pthread_mutex_lock(&bridge->output_lock);
    for (UInt32 i = 0; i < packet_list->numPackets; ++i) {
        fputs("RECV ", stdout);
        print_hex(stdout, packet->data, packet->length);
        fputc('\n', stdout);
        fflush(stdout);
        packet = MIDIPacketNext(packet);
    }
    pthread_mutex_unlock(&bridge->output_lock);
}

static void print_error(const char* operation, OSStatus status) {
    fprintf(stderr, "%s failed with OSStatus %d\n", operation, (int)status);
    fflush(stderr);
}

static int hex_value(char value) {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    return -1;
}

static size_t parse_hex(const char* text, Byte* output, size_t capacity) {
    size_t count = 0;
    int high = -1;
    for (const char* cursor = text; *cursor != '\0'; ++cursor) {
        if (*cursor == ' ' || *cursor == '\t' || *cursor == '\r' || *cursor == '\n') {
            continue;
        }
        int nibble = hex_value(*cursor);
        if (nibble < 0) return 0;
        if (high < 0) {
            high = nibble;
        } else {
            if (count >= capacity) return 0;
            output[count++] = (Byte)((high << 4) | nibble);
            high = -1;
        }
    }
    return high < 0 ? count : 0;
}

static OSStatus send_to_source(Bridge* bridge, const Byte* bytes, size_t length) {
    Byte storage[sizeof(MIDIPacketList) + MAX_PACKET];
    MIDIPacketList* list = (MIDIPacketList*)storage;
    MIDIPacket* packet = MIDIPacketListInit(list);
    packet = MIDIPacketListAdd(list, sizeof(storage), packet, 0, (UInt16)length, bytes);
    if (packet == NULL) return -1;
    return MIDIReceived(bridge->source, list);
}

static void close_bridge(Bridge* bridge) {
    if (bridge->destination != 0) {
        MIDIEndpointDispose(bridge->destination);
        bridge->destination = 0;
    }
    if (bridge->source != 0) {
        MIDIEndpointDispose(bridge->source);
        bridge->source = 0;
    }
    if (bridge->client != 0) {
        MIDIClientDispose(bridge->client);
        bridge->client = 0;
    }
    pthread_mutex_destroy(&bridge->output_lock);
}

int main(int argc, char** argv) {
    const char* source_name = argc > 1 ? argv[1] : "Mixxx API Bridge Out";
    const char* destination_name = argc > 2 ? argv[2] : "Mixxx API Bridge In";
    Bridge bridge = {0};
    pthread_mutex_init(&bridge.output_lock, NULL);

    OSStatus status = MIDIClientCreate(CFSTR("Mixxx API Bridge"), NULL, NULL, &bridge.client);
    if (status != noErr) {
        print_error("MIDIClientCreate", status);
        close_bridge(&bridge);
        return 2;
    }
    status = MIDISourceCreate(bridge.client, CFStringCreateWithCString(NULL, source_name, kCFStringEncodingUTF8), &bridge.source);
    if (status != noErr) {
        print_error("MIDISourceCreate", status);
        close_bridge(&bridge);
        return 2;
    }
    status = MIDIDestinationCreate(bridge.client,
            CFStringCreateWithCString(NULL, destination_name, kCFStringEncodingUTF8),
            read_proc,
            &bridge,
            &bridge.destination);
    if (status != noErr) {
        print_error("MIDIDestinationCreate", status);
        close_bridge(&bridge);
        return 2;
    }

    printf("READY %s %s\n", source_name, destination_name);
    fflush(stdout);

    char line[MAX_LINE];
    while (fgets(line, sizeof(line), stdin) != NULL) {
        if (strncmp(line, "QUIT", 4) == 0) break;
        if (strncmp(line, "SEND ", 5) != 0) continue;
        Byte bytes[MAX_PACKET];
        size_t length = parse_hex(line + 5, bytes, sizeof(bytes));
        if (length == 0 || length > UINT16_MAX) {
            fprintf(stderr, "invalid SEND payload\n");
            fflush(stderr);
            continue;
        }
        status = send_to_source(&bridge, bytes, length);
        if (status != noErr) print_error("MIDIReceived", status);
    }

    close_bridge(&bridge);
    return 0;
}
