python3 ../simulator/device_simulator.py --config config.yaml --ground-truth ground_truth.log --number 0 > ../iot-controller/fifo-0.fifo &


docker run -d --name local-mqtt -p 1883:1883 eclipse-mosquitto

sudo apt install mosquitto-clients

python3 controller.py --fifo-path ./ --mqtt-host localhost --mqtt-port 1883 --topic "iot/devices/batch"