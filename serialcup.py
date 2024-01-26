import datetime
import os
import queue
import re
import serial
import sys
import threading
import time
from serial.tools import list_ports

MAX_FILE_SEC = 3600

def list_serial_ports():
    available_ports = [port for port in list_ports.comports()]
    for port in available_ports:
        print(f"{port} S/N: {port.serial_number}")

def get_port_by_sn(serial_number):
    for port in list_ports.comports():
        if port.serial_number == serial_number:
            return port
    return None

def epoch_ms():
    return int(round(time.time() * 1000))

def to_epoch_ms(arg):
    # Epoch in seconds (10 digits)
    if arg.isdigit() and len(arg) == 10:
        return int(arg) * 1000

    # Epoch in milliseconds (13 digits)
    elif arg.isdigit() and len(arg) == 13:
        return int(arg)

    # Formatted date time
    elif re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", arg):
        dt = datetime.datetime.strptime(arg, "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp() * 1000)

    # Current time
    elif arg == "now":
        return int(datetime.datetime.now().timestamp() * 1000)

    # Time subtraction
    elif re.match(r"now-\d+[smhd]", arg):
        now = datetime.datetime.now()
        amount, unit = int(re.search(r"\d+", arg).group()), arg[-1]
        if unit == 's':
            delta = datetime.timedelta(seconds=amount)
        elif unit == 'm':
            delta = datetime.timedelta(minutes=amount)
        elif unit == 'h':
            delta = datetime.timedelta(hours=amount)
        elif unit == 'd':
            delta = datetime.timedelta(days=amount)
        else:
            raise ValueError("Invalid time unit in argument.")
        return int((now - delta).timestamp() * 1000)

    else:
        return None

def capture_serial_data(base_dir, serial_number, baud_rate):
    os.makedirs(base_dir, exist_ok=True)
    port = get_port_by_sn(serial_number)
    if not port:
        print("ERROR: No port found with device S/N " + serial_number)
        exit(1)
    ser = serial.Serial(port.device, baud_rate, timeout=1)

    user_input_queue = queue.Queue()
    is_paused = False

    def user_input_thread():
        while True:
            user_input = input()  # Wait for user input
            user_input_queue.put(user_input)

    threading.Thread(target=user_input_thread, daemon=True).start()

    def new_file_path():
        nonlocal base_dir, serial_number
        return os.path.join(base_dir, f"{serial_number}.{time.strftime('%Y_%m_%d_%H%M')}.{round(time.time())}.txt")

    file_start_time = time.time()
    current_file = open(new_file_path(), 'a')

    def write(data):
        nonlocal current_file, file_start_time
        current_time = time.time()
        if current_time - file_start_time >= MAX_FILE_SEC:
            current_file.close()
            current_file = open(new_file_path(), 'a')
            file_start_time = current_time

        line = str(epoch_ms()) + ',' + data + '\n'
        current_file.write(line)
        current_file.flush()
        return line

    try:
        print('> STARTED capture')
        print('> - Hit <Enter> to pause/resume')
        print('> - Type text and hit <Enter> to insert a line into a file with captured data')
        while True:
            # avoiding busy loop when paused: it can only be unpaused with input
            while not user_input_queue.empty() or is_paused:
                user_input = user_input_queue.get()
                # Toggle pause on empty line (user presses "enter")
                if user_input == "":
                    is_paused = not is_paused
                    if is_paused:
                        print("> PAUSED capture")
                    else:
                        print("> RESUMED capture")
                else:
                    line = write(user_input)
                    print("> INSERTED: " + line[:-1])

            if not is_paused:
                # Capture and write serial data to the file
                data = ser.readline().decode().strip()
                if data:
                    write(data)

    except KeyboardInterrupt:
        print()
        print("> STOPPED capture")
    finally:
        ser.close()


def query(dir, serial_number, range_start, range_end, processFunc):
    start_epoch_ms = to_epoch_ms(range_start)
    start_mark = range_start if not start_epoch_ms else None
    inside_mark = False if start_mark else True
    end_epoch_ms = to_epoch_ms(range_end)
    end_mark = range_end if not end_epoch_ms else None
    for filename in sorted(os.listdir(dir)):
        if filename.startswith(serial_number):
            file_epoch_sec = int(filename.split('.')[2])
            if start_epoch_ms and (file_epoch_sec + MAX_FILE_SEC) < start_epoch_ms // 1000:
                continue
            if end_epoch_ms and file_epoch_sec > end_epoch_ms // 1000:
                continue

            with open(os.path.join(dir, filename), 'r') as file:
                for line in file:
                    line_parts = line.strip().split(',', 1)
                    line_epoch_ms = int(line_parts[0])

                    if start_epoch_ms and line_epoch_ms < start_epoch_ms:
                        continue
                    if end_epoch_ms and line_epoch_ms > end_epoch_ms:
                        continue

                    if not inside_mark:
                        if start_mark == line_parts[1]:
                            inside_mark = True
                            continue
                    else:
                        if end_mark == line_parts[1]:
                            inside_mark = False
                            continue

                    if not inside_mark:
                        continue

                    processFunc(line.strip())

def main():
    if len(sys.argv) < 2:
        print("Usage: serialcup.py <command> [options]")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'list':
        list_serial_ports()
    elif command == 'capture':
        if len(sys.argv) != 5:
            print("""
Usage: serialcup.py capture <dir> <serial_number> <baud_rate>""")
            sys.exit(1)
        base_dir = sys.argv[2]
        serial_number = sys.argv[3]
        baud_rate = sys.argv[4]
        capture_serial_data(base_dir, serial_number, baud_rate)
    elif command == 'query':
        if len(sys.argv) < 6 or len(sys.argv) > 8:
            print("""
Usage: serialcup.py query <dir> <serial_number> <range_start> <range_end> [<match_regex> [<replace_str>]]

Arguments:
  <dir>            - Directory with captured data.
  <serial_number>  - Serial number of the device.
  <range_start>    - Start of the selection range, specified as:
                     - Label string
                     - Time, in various formats:
                       * Unix timestamp (seconds or milliseconds since 1970-01-01 00:00:00 UTC)
                       * Datetime in 'YYYY-MM-DD HH:MI:SS' format
                       * 'now' and 'now-10m' notation (where 'd' = days, 'h' = hours, 'm' = minutes, 's' = seconds)
  <range_end>      - End of the selection range, specified in the same formats as <range_start>.

Optional Arguments:
  [<match_regex>]  - A regex pattern to filter the lines.
  [<replace_str>]  - A string for formatting the line. Supports groups captured in <match_regex>.

Examples:
  serialcup.py query /tmp/serialcup 242353135363516111A1 now-1h now
  serialcup.py query /tmp/serialcup 242353135363516111A1 label1 label2 '([0-9]+),.*' 'timestamp:\1'""")
            sys.exit(1)
        base_dir = sys.argv[2]
        serial_number = sys.argv[3]
        range_start = sys.argv[4]
        range_end = sys.argv[5]
        match_regex = re.compile(sys.argv[6]) if len(sys.argv) > 6 else None
        replace_str = sys.argv[7] if len(sys.argv) > 7 else None

        def printFunc(line):
            nonlocal match_regex, replace_str
            if match_regex and not match_regex.search(line):
                return
            if match_regex and replace_str:
                print(match_regex.sub(replace_str, line))
                return
            print(line)

        query(base_dir, serial_number, range_start, range_end, printFunc)
    else:
        print("Invalid command. Use 'list', 'capture', or 'query'.")

if __name__ == '__main__':
    main()
