# SPDX-FileCopyrightText: Copyright (c) 2022 Kattni Rembor for Adafruit Industries
# SPDX-License-Identifier: Unlicense
# Code hacked together by UrbanAtWork School Year: 2025-2026
# Complete Crash Sensor Logger using Adafruit Feather RP2040, ADXL375 Accelerometer, DS3231 RTC, and SD Card

###############################s###########################################
# SAMPLING FREQUENCY  (how freqently it asks the sensors for data, seconds)
sampleRate = 0.1  # Time between readings in seconds

# ======== IMPORT LIBRARIES ========
import time             # time library for delays and timekeeping
import board            # board pin definitions
import adafruit_adxl37x # Accelerometer library
import adafruit_ds3231  # Real Time Clock (RTC) library
import digitalio        # for digital input/output
import neopixel         # for the NeoPixel RGB LED
import busio            # for SPI communication with SD card
import adafruit_sdcard  # for SD card handling
import storage          # for mounting the SD card

# ==============================================
# ======== Declare Variables ========
# ==============================================
days = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday") # a list for day reference
t = 0                   # placeholder variable for the time from the RTC hardware
activeLogging = False   # A variable to toggle between logging and not logging mode

# Data buffering variables
data_buffer = []  # List to store sensor readings before writing to SD
BUFFER_SIZE = 10  # Number of readings to collect before writing to SD
buffer_count = 0  # Counter for current buffer size
#sampleRate = 0.1  # Time between readings in seconds
sd_retry_counter = 0  # Counter for SD retry attempts

# ==============================================
# setup and define the connections and hardware
# ==============================================
i2c = board.STEMMA_I2C()        # i2c protocol to use the built-in STEMMA QT connectors on a microcontroller
rtc = adafruit_ds3231.DS3231(i2c)               # The Real Time Clock (RTC) board
accelerometer = adafruit_adxl37x.ADXL375(i2c)   # The Accelerometer breakout board

# ==============================================
# =====  DEFINE VARIABLES and HARDWARE ======
# ==============================================
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)    # The RGB (Red, Green, Blue) LED (Light Emitting Diode) on board
pixel.brightness = 0.1                          # range from 0 to 1

led = digitalio.DigitalInOut(board.LED)         # on board led by charging port
led.direction = digitalio.Direction.OUTPUT      # defining it as an OUTPUT

button = digitalio.DigitalInOut(board.BUTTON)   # The "boot" button, that can be used for the logging toggle on/off
button.switch_to_input(pull=digitalio.Pull.UP)  # Define the button as an INPUT

# ==============================================
# ===== SD CARD SETUP ======
# ==============================================
sd_mounted = False
try:
    # SD card SPI setup for Feather RP2040 Adalogger
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    cs = digitalio.DigitalInOut(board.D10)  # SD card chip select pin
    sdcard = adafruit_sdcard.SDCard(spi, cs)
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, "/sd")

    # Remount as writable (this is the key fix!)
    storage.remount("/sd", readonly=False)
    sd_mounted = True
    print("SD card mounted successfully (writable)")

    # Create log file with header if it doesn't exist
    try:
        with open("/sd/crash_log.txt", "r") as f:
            pass  # File exists
    except OSError:
        # File doesn't exist, create with header
        with open("/sd/crash_log.txt", "w") as f:
            f.write("Date, Time, X_accel, Y_accel, Z_accel\\n")
        print("Created new log file with header")

except Exception as e:
    print(f"SD card setup failed: {e}")
    sd_mounted = False

####################################################

####################################################

print("System Test # ==============================================")
print("Crash Code Logger Initialized")
#print("Press the button to start/stop logging")

#################################################
## ZERO out what the accelerometer readings    ##
#################################################
def zeroAccel():
    """Function to zero the accelerometer readings."""
    print("Zeroing Accelerometer... Please keep the board still.")
    time.sleep(2)
    accelerometer.zero_g_offset_x = accelerometer.acceleration[0]
    accelerometer.zero_g_offset_y = accelerometer.acceleration[1]
    accelerometer.zero_g_offset_z = accelerometer.acceleration[2]
    print("Accelerometer Zeroed.")
    print("==============================================")

zeroAccel()

# ==============================================
# =====  DEFINE logging FUNCTION ======
# ==============================================
def logData():
    """Function to log the data from the accelerometer and RTC."""
    global t
    x, y, z = accelerometer.acceleration  # read the acceleration values
    t = rtc.datetime  # read the current date and time from the RTC
    # print the data to the console
    print(f"{days[t.tm_wday]}, {t.tm_mon}/{t.tm_mday}/{t.tm_year} {t.tm_hour}:{t.tm_min}:{t.tm_sec}, X: {x:.2f} m/s², Y: {y:.2f} m/s², Z: {z:.2f} m/s²")
    #print(f"({x:.2f},{y:.2f},{z:.2f})")  # Uncomment this to use the "Mu editor python plotter"

##############################
## Define Buffer FUNCTION
##############################
def bufferData():
    """Function to buffer accelerometer data and write to SD when buffer is full."""
    global data_buffer, buffer_count, t

    # Read current sensor data
    x, y, z = accelerometer.acceleration
    t = rtc.datetime

    # Create formatted data string
    data_line = f"{days[t.tm_wday]}, {t.tm_mon}/{t.tm_mday}/{t.tm_year} {t.tm_hour}:{t.tm_min:02}:{t.tm_sec:02}, X: {x:.2f}, Y: {y:.2f}, Z: {z:.2f}"

    # Add to buffer
    data_buffer.append(data_line)
    buffer_count += 1

    # Write to SD card when buffer is full
    if buffer_count >= BUFFER_SIZE:
        writeBufferToSD()

def writeBufferToSD():
    """Write all buffered data to SD card and clear buffer."""
    global data_buffer, buffer_count, sd_mounted

    if not sd_mounted:
        print("SD card not available - data remains in buffer")
        return

    if buffer_count == 0:
        print("Buffer is empty - nothing to write")
        return

    try:
        with open("/sd/crash_log.txt", "a") as f:
            for data_line in data_buffer:
                f.write(data_line + "\n")
        print(f"Wrote {buffer_count} readings to SD card")

        # Clear buffer after successful write
        data_buffer = []
        buffer_count = 0

    except Exception as e:
        print(f"SD write error: {e}")
        print("Data remains in buffer for retry")
        # Keep buffer data for retry

def forceWriteBuffer():
    """Force write buffer to SD card regardless of buffer size (for emergencies)."""
    global buffer_count
    if buffer_count > 0:
        writeBufferToSD()
        print("Emergency buffer flush completed")

def retrySDMount():
    """Attempt to remount SD card if it failed initially."""
    global sd_mounted, spi, cs, sdcard, vfs

    if sd_mounted:
        return True

    try:
        print("Attempting to remount SD card...")
        sdcard = adafruit_sdcard.SDCard(spi, cs)
        vfs = storage.VfsFat(sdcard)
        storage.mount(vfs, "/sd")
        storage.remount("/sd", readonly=False)
        sd_mounted = True
        print("SD card remounted successfully")
        return True
    except Exception as e:
        print(f"SD remount failed: {e}")
        return False

def detectCrash():
    """Simple crash detection based on acceleration threshold."""
    x, y, z = accelerometer.acceleration
    # Calculate total acceleration magnitude
    total_accel = (x**2 + y**2 + z**2)**0.5

    # Crash threshold (adjust based on testing) - ADXL375 can detect up to 200g
    CRASH_THRESHOLD = 50.0  # m/s²

    if total_accel > CRASH_THRESHOLD:
        print(f"CRASH DETECTED! Acceleration: {total_accel:.2f} m/s²")
        pixel.fill((255, 0, 0))  # Red alert
        forceWriteBuffer()  # Immediately save all buffered data
        return True
    return False


# ==============================================
# =====        MAIN PROGRAM LOOP !!       ======
# ==============================================
while True:
    if not button.value:  # button is pressed
        activeLogging = not activeLogging  # toggle the logging state
        if activeLogging:
            print("Logging is now ACTIVE")
            pixel.fill((0, 255, 0))  # Green
            time.sleep(3)
        else:
            print("Logging is now INACTIVE")
            pixel.fill((255, 255, 0))  # Yellow
            time.sleep(3)  # debounce delay

    if activeLogging:
        logData()      # Print to console
        bufferData()   # Add to buffer and write to SD when full

        # Check for crash (always monitor, even when not actively logging)
        if detectCrash():
            activeLogging = True  # Force logging on if crash detected

    # Periodically retry SD mount if it failed (every 50 loops)
    if not sd_mounted:
        sd_retry_counter += 1
        if sd_retry_counter >= 50:
            retrySDMount()
            sd_retry_counter = 0

    time.sleep(sampleRate)  # Wait between readings

