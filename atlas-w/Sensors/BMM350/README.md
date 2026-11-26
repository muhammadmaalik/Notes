#BMM350 -- 3-Axis Magnetic Sensor

* Using this sensor as my compass, it's Voltage in is about 1.72-1.98V, absolute max is 2.0V
* 0.2 mA at 100 Hz, peak is 3.5 mA
* 1.8V from 3.3V rail, own LDO for stepping down voltage.
* Device Pin = MAG_INT , PC10 MCU Pin, board has a 10k pull up resistor.
* Make sure the 22uF cap, which is on the MAG_CRST, should be as close to the value as possible please make sure of that.


