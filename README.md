# SerialCup

SerialCup is a handy small script to save and query/format serial port data (from Arduino/ESP32/etc). E.g. when extracting (especially repeatedly) CSV file of a sensor readings for multiple tests. Avoids scrolling in and copy-pasting from Serial Monitor, but not just that. You can optionally control formatting by supplying regular expressions or by writing some Python code (for more custom control, if really need to). Runs on Windows, MacOS, Linux, etc.

Has two main functions:
* capture: captures data from serial port into a file
    * prefixes lines with a timestamp
    * rolls to a new file every 1h to keep size manageable (keeps all history)
    * allows to pause/resume capturing with one key press
    * allows to insert a line into captured data (e.g. to "label" boundaries of different tests)
* query: extracts specified range from captured data files and optionally formats the result
    * range can be time range or "between labels"
    * can filter lines using standard regex
    * can format output using standard match+replace regex

As an additional perk, since data is saved locally and this is a Python "lib", you can query and process data with Python script for further flexibility and control. It's also easy to do stats and even ML with standard Python tools like Pandas, NumPy, and in Jupyter Notebooks.

### Quick how-to

Python and `pyserial` lib are required. Once Python is installed, you can install `pyserial` with

```commandline
pip3 install pyserial
```

Connect a thing (e.g. Arduino/ESP32/etc.) via USB. List ports with:

```commandline
% python3 serialcup.py list

/dev/cu.Bluetooth-Incoming-Port - n/a S/N: None
/dev/cu.usbmodem101 - IOUSBHostDevice S/N: 242353135363516111A1
```

Pick destination for saving the data, your device's S/N and baudrate, and start capturing:

```commandline
% python3 serialcup.py capture /tmp/serialcup 242353135363516111A1 9600

> STARTED capture
> - Hit <Enter> to pause/resume
> - Type text and hit <Enter> to insert a line into a file with captured data
test1-start
> INSERTED: 1705318467232,test1-start
test1-end
> INSERTED: 1705318472233,test1-end
^C
> STOPPED capture
```

In the above the `test1-start` and `test1-stop` lines where inserted into the data (by entering the lines while data was captured) to "label" the start and end of the test.

The data printed to serial port is saved into files prefixed with epochMs:

```text
...
1705318466230,Measurement #1
1705318466230,temp:13.90,humi:32.50
1705318467232,test1-start
1705318468234,Measurement #2
1705318469234,temp:14.00,humi:33.00
1705318470235,Measurement #3
1705318471235,temp:14.10,humi:33.50
1705318472233,test1-end
1705318473235,Measurement #3
...
```

To extract lines between `test1-start` and `test1-end`:
```commandline
% python3 serialcup.py query /tmp/serialcup 242353135363516111A1 test1-start test1-end

1705318468234,Measurement #2
1705318469234,temp:14.00,humi:33.00
1705318470235,Measurement #3
1705318471235,temp:14.10,humi:33.50
```

You can also specify any of the start or the end of the range using the time instead of "label". The script accepts any of: unix timestamp (seconds or milliseconds since 1970-01-01 00:00:00 UTC); datetime in `YYYY-MM-DD HH:MI:SS` format; `now` and `now-10m` notation (`d` - days, `h` - hours, `m` - minutes, `s` - seconds).

To filter only the lines with `temp` you add a filter regex argument:

```commandline
% python3 serialcup.py query /tmp/serialcup 242353135363516111A1 test1-start test1-end '.*temp.*'

1705318469234,temp:14.00,humi:33.00
1705318471235,temp:14.10,humi:33.50
```

Now let's format the lines as rows in CSV file:

```commandline
% python3 serialcup.py query /tmp/serialcup 242353135363516111A1 test1-start test1-end '([0-9]+),.*temp:([0-9]+[.]*[0-9]*).*' '\1,\2'

1705318469234,14.00
1705318471235,14.10
```

In this case, `([0-9]+),.*temp:([0-9]+[.]*[0-9]*).*` matches the lines with `temp:` and additionally captures the timestamp (`([\d]+)`) and a temp reading value (`([\d.]+)`) as groups, while `\1,\2` instructs to output the captured groups with comma between them.

Now, to tie all of this together, to extract a CSV file with temperature readings between `test1-start` and `test1-end` marks, that looks like this:
```text
epochMs,temp
1705318469234,14.00
1705318471235,14.10
```
do:
```commandline
echo "epochMs,temp" > /tmp/temp.csv &&
python3 serialcup.py query /tmp/serialcup 242353135363516111A1 test1-start test1-end '([0-9]+),.*temp:([0-9]+[.]*[0-9]*).*' '\1,\2' >> /tmp/temp.csv
```

If you'd rather write Python code to process the data, you can do that as well. E.g. this code replaces epochMs with ms passed since previous recording and prints out the lines:

```python
import serialcup

def processFunc(line):
  global prev_epoch_ms
  epoch_ms = int(line[:13])
  delta_ms = epoch_ms - prev_epoch_ms
  prev_epoch_ms = epoch_ms
  print(str(delta_ms) + line[13:])

serialcup.query('/tmp/serialcup', '242353135363516111A1', 'now-10m', 'now', processFunc)
```

On the way out, if you found this useful, you may also want to check out https://github.com/sensortea/CupLogger - a more sophisticated tool to capture and visualize serial port data.

### <a name="support"></a>Follow and support

Follow this project or [sensortea](https://github.com/sensortea) on github or [@sensortea](https://twitter.com/sensortea) on Twitter (X).

A great help is sharing what didn't work for you or what must be improved.

The best help is sharing if this project is useful, e.g. by starring it here on Github. You could also send a note to info_at_sensortea_dot_com.

### <a name="license"></a> License

This project is distributed under the MIT License. See the LICENSE file for more details.
