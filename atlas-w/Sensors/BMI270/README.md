* I'm using a BMI270 as my IM -- I2C protocol
  Normal current draw is 0.685 mA -- connected to 3.3V rail from the Nucleo 3V3 out -- IMU_INT1 = BMI270 INT1 - MCU Pin PA0 - D4 = CN 9-5 -- in, interrupt line 0 -- Notes = Set BMI270 INT1 to push-pull, active high, PA0 can also wake the chip.
  The entire wiring scheme for the IMU is on file.
