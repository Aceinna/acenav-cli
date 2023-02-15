set PYTHONPATH=.;./src/aceinna/devices/widgets;%PYTHONPATH%
set PATH=./src/aceinna/devices/widgets/can/interfaces/bmcan;%PATH%

python main.py -i canfd %2

@echo kill python driver...