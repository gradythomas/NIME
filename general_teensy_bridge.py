import serial, serial.tools.list_ports, socket, sys
from pythonosc import osc_message_builder
from pythonosc import udp_client
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import asyncio

# Header ID's of messages recieved from the Teensy
BUTTON_CH_0 = 0
BUTTON_CH_1 = 1
BUTTON_CH_2 = 2
BUTTON_CH_3 = 3

FADER_CH_0 = 4
FADER_CH_1 = 5
FADER_CH_2 = 6
FADER_CH_3 = 7
FADER_CH_4 = 8
FADER_CH_5 = 9
FADER_CH_6 = 10

IMU_CH_0 = 11
IMU_CH_1 = 12
IMU_CH_2 = 13
IMU_CH_3 = 14
IMU_CH_4 = 15

# sets grouping of ID's by type
buttonIds = {
    BUTTON_CH_0,
    BUTTON_CH_1,
    BUTTON_CH_2,
    BUTTON_CH_3
}

faderIds = {
    FADER_CH_0,
    FADER_CH_1,
    FADER_CH_2,
    FADER_CH_3,
    FADER_CH_4,
    FADER_CH_5,
    FADER_CH_6
}

ImuIds = {
    IMU_CH_0,
    IMU_CH_1,
    IMU_CH_2,
    IMU_CH_3,
    IMU_CH_4
}

#set up serial port
ports = list(serial.tools.list_ports.comports())

for port in ports:
    if ("USB Serial" in port.description): #Teensy description is "USB Serial Device"
        ser = serial.Serial(port.device)
        ser.baudrate=57600
        ser.read(ser.in_waiting) # if anything in input buffer, discard it


#initialize UDP client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
# dispatcher in charge of executing functions in response to RECIEVED OSC messages
dispatcher = Dispatcher()

def readNextMessage():
    #buffer to decode message into (reading from serial port)
    bytesTotal = bytes()

    # if escape flag is true, next byte is part of message (even if a reserved byte)
    escFlag = False

    curByte = bytes()
    # defines reserved bytes signifying end of message and escape character
    endByte = bytes([255])
    escByte = bytes([254])

    while (ser.in_waiting):
        curByte = ser.read()
        if (escFlag):
            bytesTotal += curByte
            escFlag = False
        elif (curByte == endByte):
            #if we reach a true end byte, we've read a full message, return buffer
            return bytesTotal
        elif (curByte == escByte):
            # if we reach a true escape byte, set the flag, but don't write the reserved byte to the buffer
            escFlag = True
        else:
            bytesTotal += curByte

def buttonToPd(ch, x, y, z, state):
    address = "/button/ch{}/x{}/y{}/z{}".format(ch, x, y, z)
    client.send_message(address, state)

def faderToPd(ch, x, y, value):
    address = "/fader/ch{}/x{}/y{}".format(ch, x, y)
    client.send_message(address, value)

def interpretMessage(message):
    if (message == None):
        return
    elif (message[0] in buttonIds):
        # based on byte order of msg type, interpret what kind of data we have recieved
        channel = message[0] - BUTTON_CH_0
        x = message[1]
        y = message[2]
        z = message[3]
        state = message[4]
        buttonToPd(channel, x, y, z, state)
    elif (message[0] in faderIds):
        channel = message[0] - FADER_CH_0
        x = message[1]
        y = message[2]
        highValByte = message[3]
        lowValByte = message[4]
        signed = message[5]
        value = (highValByte << 8) + lowValByte
        if (signed):
            value = value - 32768
        faderToPd(channel, x, y, value)

async def loop():
    while(1):
        currentMessage = readNextMessage() # can be None if nothing in input buffer
        interpretMessage(currentMessage)
        #allows dispatcher to take over and check for recieved OSC messages
        await asyncio.sleep(0)

async def init_main():
    server = AsyncIOOSCUDPServer(("127.0.0.1", 5006), dispatcher, asyncio.get_event_loop())
    transport, protocol = await server.create_serve_endpoint()
    await loop()
    transport.close()

asyncio.run(init_main())
