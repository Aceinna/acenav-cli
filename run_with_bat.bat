set PYTHONPATH=.;./src/aceinna/devices/widgets;%PYTHONPATH%

python main.py -i canfd %1

@echo kill python driver...